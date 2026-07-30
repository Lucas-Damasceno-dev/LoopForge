"""Renderizadores do Codebase Genome para múltiplos formatos (Markdown, Summary, JSON)."""

import json
from genome.store.models import Genome


def render_markdown(genome: Genome) -> str:
    lines = []
    lines.append(f"# 🧬 Codebase Genome v{genome.version}")
    lines.append(f"**Root**: `{genome.repo.root}` | **Files**: {genome.repo.total_files} | **Lines**: {genome.repo.total_lines}")
    lines.append("")

    # Linguagens
    lines.append("## 📊 Linguagens")
    for lang, stats in genome.repo.langs.items():
        lines.append(f"- **{lang.capitalize()}**: {stats.files} arquivos, {stats.lines} linhas")
    lines.append("")

    # Arquitetura
    lines.append("## 🏗️ Arquitetura")
    lines.append(f"- **Padrão**: `{genome.architecture.pattern}` ({genome.architecture.source})")
    if genome.architecture.layers:
        lines.append(f"- **Camadas**: `{' -> '.join(genome.architecture.layers)}`")
    if genome.architecture.layer_violations:
        lines.append(f"- ⚠️ **Violações de Camada**: {len(genome.architecture.layer_violations)}")
        for v in genome.architecture.layer_violations[:5]:
            lines.append(f"  - `{v.from_path}` -> `{v.to_path}` ({v.type})")

    # Bus Factor
    bf = genome.architecture.bus_factor
    lines.append(f"- **Bus Factor Score**: {bf.score}")
    if bf.high_risk_files:
        lines.append("  - **Arquivos Críticos (Ônibus)**:")
        for hrf in bf.high_risk_files[:5]:
            lines.append(f"    • `{hrf.path}` ({hrf.dependents} dependentes)")

    # Convenções
    lines.append("")
    lines.append("## 📐 Convenções")
    if genome.conventions.testing:
        lines.append(f"- **Testes**: {genome.conventions.testing.get('framework')} em `{genome.conventions.testing.get('location')}`")
    if genome.conventions.error_handling:
        lines.append(f"- **Tratamento de Erros**: `{genome.conventions.error_handling.pattern}`")

    # Top Módulos e Exports
    lines.append("")
    lines.append("## 📦 Top Módulos & Interfaces Exportadas")
    for mod in genome.modules[:10]:
        exports_str = ", ".join(f"`{e.name}` ({e.kind})" for e in mod.exports[:5])
        if not exports_str:
            exports_str = "Nenhum export público"
        lines.append(f"- `{mod.path}` ({mod.lines_count}L, instabilidade: {mod.instability})")
        lines.append(f"  - Exports: {exports_str}")

    return "\n".join(lines)


def render_summary(genome: Genome) -> str:
    langs = ", ".join(f"{k}:{v.files}" for k, v in genome.repo.langs.items())
    violations = len(genome.architecture.layer_violations)
    bus_risk = len(genome.architecture.bus_factor.high_risk_files)
    return (
        f"[GENOME SUMMARY] Files: {genome.repo.total_files} | Lines: {genome.repo.total_lines} | "
        f"Langs: [{langs}] | Arch: {genome.architecture.pattern} | "
        f"Layer Violations: {violations} | High Risk Files: {bus_risk} | Bus Factor: {genome.architecture.bus_factor.score}"
    )


def render_json(genome: Genome) -> str:
    return genome.model_dump_json(indent=2)
