from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command(name="release")
@click.argument("version", default="6.0.0")
@click.option("--dry-run", is_flag=True, default=False, help="Apenas exibe as notas sem atualizar o CHANGELOG.md")
def release_cmd(version: str, dry_run: bool):
    """Gera notas de release semânticas e atualiza o CHANGELOG.md."""
    now_date = datetime.now(UTC).strftime("%Y-%m-%d")

    release_notes = f"""## [{version}] - {now_date}

### 🚀 Funcionalidades
- **LangGraph Orchestration**: Migração completa da governança para StateGraph em Python.
- **Roteamento Adaptativo**: Suporte a Fast-Path (Dev -> QA) e Full-Path (CPO -> PM -> Tech Lead -> Dev -> QA).
- **Spec Review Gate**: Gate interativo para aprovação e ajuste da visão e tarefas (`lf plan`).
- **OpenRouter Native Integration**: Integração direta com modelo Ling 3.0 Flash Free (`inclusionai/ling-3.0-flash:free`).

### 🛡️ Governança & Segurança
- Circuit Breaker com limite orçamentário (USD).
- Security Scanner integrado com auto-fix para secrets e código perigoso.
- Telemetria SQLite e checkpointing persistente por sessão.
"""

    if dry_run:
        console.print("[bold yellow]--- NOTAS DE RELEASE (DRY RUN) ---[/bold yellow]")
        console.print(release_notes)
        return

    changelog_path = Path("CHANGELOG.md")
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        new_content = f"# Changelog\n\n{release_notes}\n" + existing.replace("# Changelog\n\n", "")
    else:
        new_content = f"# Changelog\n\n{release_notes}\n"

    changelog_path.write_text(new_content, encoding="utf-8")
    console.print(f"[bold green]✓ Versão {version} lançada e registrada no CHANGELOG.md com sucesso![/bold green]")
