"""Scanner principal para varredura de repositório e construção do Codebase Genome."""

from datetime import datetime, timezone
import hashlib
import os
from typing import Dict, List, Set
from genome.core.architecture import ArchitectureChecker
from genome.core.bus_factor import calculate_bus_factor
from genome.core.conventions import infer_conventions
from genome.core.graph import build_dependency_graph, compute_metrics, detect_circular_dependencies
from genome.languages.base import BaseLanguageScanner
from genome.languages.python import PythonScanner
from genome.languages.typescript import TypeScriptScanner
from genome.resolvers.base import BaseSymbolResolver
from genome.resolvers.py_resolver import PythonSymbolResolver
from genome.resolvers.ts_resolver import TypeScriptSymbolResolver
from genome.store.models import Genome, LanguageStats, ModuleInfo, RepoMetadata
from genome.store.sqlite import GenomeStore


class GenomeScanner:
    _registered_scanners: List[BaseLanguageScanner] = [PythonScanner(), TypeScriptScanner()]
    _registered_resolvers: List[BaseSymbolResolver] = [PythonSymbolResolver(), TypeScriptSymbolResolver()]

    @classmethod
    def register_scanner(cls, scanner: BaseLanguageScanner) -> None:
        cls._registered_scanners.append(scanner)

    @classmethod
    def register_resolver(cls, resolver: BaseSymbolResolver) -> None:
        cls._registered_resolvers.append(resolver)

    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.scanners = list(self._registered_scanners)
        self.resolvers = list(self._registered_resolvers)

    def _should_ignore(self, rel_path: str) -> bool:
        ignore_dirs = {
            ".git",
            ".genome",
            ".loopforge",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
        }
        parts = rel_path.split(os.sep)
        return any(p in ignore_dirs for p in parts)

    def scan(self, incremental: bool = False) -> Genome:
        store = GenomeStore(self.repo_root)
        cached_genome = store.load_genome() if incremental else None

        known_files: Set[str] = set()
        file_paths: List[str] = []

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [
                d for d in dirs if not self._should_ignore(os.path.relpath(os.path.join(root, d), self.repo_root))
            ]
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.repo_root)
                if not self._should_ignore(rel_path):
                    known_files.add(rel_path)
                    file_paths.append(rel_path)

        modules: List[ModuleInfo] = []
        lang_stats: Dict[str, LanguageStats] = {}
        total_lines = 0

        for rel_path in file_paths:
            full_path = os.path.join(self.repo_root, rel_path)

            matched_scanner = None
            for scanner in self.scanners:
                if scanner.can_handle(rel_path):
                    matched_scanner = scanner
                    break

            if not matched_scanner:
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except Exception:
                continue

            mod_info = matched_scanner.scan_file(rel_path, code)
            modules.append(mod_info)

            # Atualizar estatísticas de linguagem
            lang = matched_scanner.language_name
            if lang not in lang_stats:
                lang_stats[lang] = LanguageStats(files=0, lines=0)
            lang_stats[lang].files += 1
            lang_stats[lang].lines += mod_info.lines_count
            total_lines += mod_info.lines_count

            # Atualizar hash para incremental
            file_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
            mtime = os.path.getmtime(full_path)
            store.update_file_hash(rel_path, file_hash, mtime)

        # 2. Resolução de Símbolos / Dependências entre módulos
        for mod in modules:
            deps: Set[str] = set()
            for resolver in self.resolvers:
                resolved = resolver.resolve_dependencies(mod, self.repo_root, known_files)
                deps.update(resolved)
            mod.dependencies = sorted(list(deps))

        # 3. Grafo de Dependências e Métricas
        graph = build_dependency_graph(modules)
        modules = compute_metrics(graph, modules)
        circular_deps = detect_circular_dependencies(graph)

        # 4. Bus Factor
        bus_factor = calculate_bus_factor(graph, modules)

        # 5. Arquitetura e Validação de Camadas
        arch_checker = ArchitectureChecker(self.repo_root)
        arch = arch_checker.check_architecture(modules, bus_factor, circular_deps)

        # 6. Convenções
        conventions = infer_conventions(modules)

        repo_meta = RepoMetadata(
            root=self.repo_root,
            langs=lang_stats,
            total_files=len(modules),
            total_lines=total_lines,
        )

        genome = Genome(
            version="1.0.0",
            repo=repo_meta,
            conventions=conventions,
            modules=modules,
            architecture=arch,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        store.save_genome(genome)
        return genome
