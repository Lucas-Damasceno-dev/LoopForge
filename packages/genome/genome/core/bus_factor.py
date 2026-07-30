"""Cálculo do Bus Factor e identificação de módulos de alto risco ("ônibus")."""

from typing import List
import networkx as nx
from genome.store.models import BusFactor, HighRiskFile, ModuleInfo


def calculate_bus_factor(graph: nx.DiGraph, modules: List[ModuleInfo], high_risk_threshold: int = 10) -> BusFactor:
    high_risk_files: List[HighRiskFile] = []

    for mod in modules:
        num_dependents = len(mod.dependents)
        if num_dependents >= high_risk_threshold:
            high_risk_files.append(
                HighRiskFile(path=mod.path, dependents=num_dependents, owners=1)
            )

    high_risk_files.sort(key=lambda x: x.dependents, reverse=True)

    # Score de Bus Factor (1.0 = saudável, <0.5 = muitos arquivos críticos concentrados)
    if not modules:
        score = 1.0
    else:
        critical_ratio = len(high_risk_files) / max(len(modules), 1)
        score = round(max(0.0, 1.0 - (critical_ratio * 3.0)), 2)

    return BusFactor(score=score, high_risk_files=high_risk_files)
