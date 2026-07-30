"""Leitor de .genomerc e validador de regras de camadas/arquitetura."""

import os
from typing import Any, Dict, List, Optional
try:
    import tomllib  # Python 3.11+
except ImportError:
    import json as tomllib  # type: ignore

from genome.store.models import Architecture, BusFactor, LayerViolation, ModuleInfo


class ArchitectureChecker:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.genomerc_path = os.path.join(self.repo_root, ".genomerc")

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.genomerc_path):
            return {}

        try:
            with open(self.genomerc_path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def check_architecture(
        self, modules: List[ModuleInfo], bus_factor: BusFactor, circular_deps: List[List[str]]
    ) -> Architecture:
        config = self.load_config()
        arch_config = config.get("architecture", {})

        pattern = arch_config.get("pattern", "custom")
        layers = arch_config.get("layers", [])
        rules = arch_config.get("rules", [])

        violations: List[LayerViolation] = []

        # Validação de regras de camada declaradas
        mod_map = {m.path: m for m in modules}

        for rule in rules:
            from_layer = rule.get("from")
            cannot_depend = set(rule.get("cannot_depend_on", []))

            for mod_path, mod in mod_map.items():
                if from_layer and from_layer in mod_path.split(os.sep):
                    for dep in mod.dependencies:
                        dep_parts = dep.split(os.sep)
                        for forbidden in cannot_depend:
                            if forbidden in dep_parts:
                                violations.append(
                                    LayerViolation(
                                        from_path=mod_path,
                                        to_path=dep,
                                        type=f"illegal-boundary: '{from_layer}' cannot depend on '{forbidden}'",
                                    )
                                )

        return Architecture(
            pattern=pattern,
            source=".genomerc" if os.path.exists(self.genomerc_path) else "auto-detected",
            layers=layers,
            layer_violations=violations,
            circular_deps=circular_deps,
            bus_factor=bus_factor,
        )
