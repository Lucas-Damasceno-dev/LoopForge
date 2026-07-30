"""Resolvedor de importações Python para caminhos de arquivos locais."""

import os
from typing import List, Set
from genome.resolvers.base import BaseSymbolResolver
from genome.store.models import ModuleInfo


class PythonSymbolResolver(BaseSymbolResolver):
    def resolve_dependencies(
        self, module: ModuleInfo, repo_root: str, known_files: Set[str]
    ) -> List[str]:
        if module.language != "python":
            return []

        resolved: Set[str] = set()

        for imp in module.imports:
            # Converter ex: lf.orchestrator.task_dispatcher -> src/lf/orchestrator/task_dispatcher.py
            parts = imp.split(".")

            # Tentar combinações com prefixos comuns como src, etc.
            possible_rel_paths = [
                os.path.join(*parts) + ".py",
                os.path.join(*parts, "__init__.py"),
                os.path.join("src", *parts) + ".py",
                os.path.join("src", *parts, "__init__.py"),
            ]

            for candidate in possible_rel_paths:
                normalized = os.path.normpath(candidate)
                if normalized in known_files and normalized != module.path:
                    resolved.add(normalized)
                    break

        return sorted(list(resolved))
