"""Resolvedor de importações TypeScript / JavaScript com suporte a tsconfig path aliases."""

import json
import os
from typing import Dict, List, Set
from genome.resolvers.base import BaseSymbolResolver
from genome.store.models import ModuleInfo


class TypeScriptSymbolResolver(BaseSymbolResolver):
    def _load_path_aliases(self, repo_root: str) -> Dict[str, str]:
        tsconfig_path = os.path.join(repo_root, "tsconfig.json")
        if not os.path.exists(tsconfig_path):
            return {}

        try:
            with open(tsconfig_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Remover comentários simples em JSON5/tsconfig
                content_clean = "\n".join(
                    line for line in content.splitlines() if not line.strip().startswith("//")
                )
                data = json.loads(content_clean)
                paths = data.get("compilerOptions", {}).get("paths", {})
                aliases: Dict[str, str] = {}
                for prefix, targets in paths.items():
                    clean_prefix = prefix.rstrip("/*")
                    if targets:
                        clean_target = targets[0].rstrip("/*")
                        aliases[clean_prefix] = clean_target
                return aliases
        except Exception:
            return {}

    def resolve_dependencies(
        self, module: ModuleInfo, repo_root: str, known_files: Set[str]
    ) -> List[str]:
        if module.language != "typescript":
            return []

        resolved: Set[str] = set()
        aliases = self._load_path_aliases(repo_root)

        for imp in module.imports:
            # 1. Resolver alias de tsconfig (ex: @/components/Header -> src/components/Header)
            target_imp = imp
            for alias_prefix, target_prefix in aliases.items():
                if imp == alias_prefix or imp.startswith(alias_prefix + "/"):
                    target_imp = imp.replace(alias_prefix, target_prefix, 1)
                    break

            # 2. Resolver import relativo (ex: ./utils, ../models)
            if target_imp.startswith("."):
                dir_name = os.path.dirname(module.path)
                candidate_base = os.path.normpath(os.path.join(dir_name, target_imp))
            else:
                candidate_base = os.path.normpath(target_imp)

            exts = [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]
            for ext in exts:
                candidate = candidate_base + ext if not candidate_base.endswith(ext) else candidate_base
                if candidate in known_files and candidate != module.path:
                    resolved.add(candidate)
                    break

        return sorted(list(resolved))
