
import click
from rich.console import Console
from rich.table import Table

from lf.guardrails.security_scanner import SecurityScanner

console = Console()


@click.command(name="audit")
@click.argument("directory", default=".", type=click.Path(exists=True))
@click.option("--fix", is_flag=True, default=False, help="Autocorrige vulnerabilidades simples encontradas")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Formato de saída")
def audit_cmd(directory: str, fix: bool, output_format: str):
    """Executa o scanner de segurança em busca de vulnerabilidades e secrets."""
    scanner = SecurityScanner()
    vulnerabilities = scanner.scan_directory(directory)

    if output_format == "json":
        import json
        data = [
            {
                "file_path": v.file_path,
                "line_number": v.line_number,
                "rule_id": v.rule_id,
                "message": v.message,
            }
            for v in vulnerabilities
        ]
        click.echo(json.dumps(data, indent=2))
        return

    if not vulnerabilities:
        console.print("[bold green]✓ Nenhuma vulnerabilidade de segurança encontrada.[/bold green]")
        return

    console.print(f"[bold red]⚠ {len(vulnerabilities)} vulnerabilidade(s) encontrada(s):[/bold red]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Regra", style="cyan", width=10)
    table.add_column("Arquivo", style="yellow")
    table.add_column("Linha", style="white", justify="right", width=6)
    table.add_column("Descrição", style="red")

    for v in vulnerabilities:
        table.add_row(v.rule_id, v.file_path, str(v.line_number), v.message)

    console.print(table)

    if fix:
        fixed = scanner.fix_vulnerabilities(directory)
        console.print(f"\n[bold green]✓ {fixed} vulnerabilidade(s) autocorrida(s).[/bold green]")
