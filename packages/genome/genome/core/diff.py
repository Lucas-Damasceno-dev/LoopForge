"""Comparador (diff) entre dois genomas."""

from typing import Any, Dict, List
from genome.store.models import Genome


def diff_genomes(old_genome: Genome, new_genome: Genome) -> Dict[str, Any]:
    old_mods = {m.path: m for m in old_genome.modules}
    new_mods = {m.path: m for m in new_genome.modules}

    added_files = list(set(new_mods.keys()) - set(old_mods.keys()))
    removed_files = list(set(old_mods.keys()) - set(new_mods.keys()))

    new_exports: List[str] = []
    removed_exports: List[str] = []

    for path, new_m in new_mods.items():
        if path in old_mods:
            old_exp_names = {e.name for e in old_mods[path].exports}
            new_exp_names = {e.name for e in new_m.exports}
            for added in new_exp_names - old_exp_names:
                new_exports.append(f"{path}::{added}")
            for removed in old_exp_names - new_exp_names:
                removed_exports.append(f"{path}::{removed}")

    bus_score_delta = round(new_genome.architecture.bus_factor.score - old_genome.architecture.bus_factor.score, 2)
    new_violations = len(new_genome.architecture.layer_violations) - len(old_genome.architecture.layer_violations)

    return {
        "added_files": added_files,
        "removed_files": removed_files,
        "new_exports": new_exports,
        "removed_exports": removed_exports,
        "bus_score_delta": bus_score_delta,
        "new_layer_violations": max(0, new_violations),
    }
