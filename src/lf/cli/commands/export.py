"""Comando CLI 'lf export' para exportar pacotes de auditoria do LoopForge v6."""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command(name="export")
@click.option("--dir", "-d", "project_dir", default=".", help="Diretório do projeto gerado para exportação")
@click.option("--output", "-o", default=None, help="Caminho do arquivo ZIP de saída (ex: audit_pack.zip)")
@click.option("--format", "fmt", type=click.Choice(["zip", "json"]), default="zip", help="Formato de exportação")
def export_cmd(project_dir: str, output: str | None, fmt: str):
    """Empacota os artefatos do projeto gerado e relatórios de auditoria em um pacote assinado."""
    target_path = Path(project_dir).resolve()

    if not target_path.exists():
        console.print(f"[bold red]Diretório {target_path} não encontrado.[/bold red]")
        raise SystemExit(1)

    out_file = output or f"loopforge_audit_{target_path.name}.zip"

    console.print(f"[bold cyan]📦 Empacotando artefatos de auditoria de: {target_path}...[/bold cyan]")

    files_to_pack = []
    manifest_entries = []

    for root, _, files in os.walk(target_path):
        for f in files:
            if f.endswith((".pyc", ".git", ".db", ".sqlite")):
                continue
            full_file = Path(root) / f
            rel_file = full_file.relative_to(target_path)

            try:
                content = full_file.read_bytes()
                sha256 = hashlib.sha256(content).hexdigest()
                manifest_entries.append({
                    "path": str(rel_file),
                    "size_bytes": len(content),
                    "sha256": sha256,
                })
                files_to_pack.append((full_file, rel_file))
            except Exception as e:
                console.print(f"[yellow]Aviso ao ler {rel_file}: {e}[/yellow]")

    manifest_data = {
        "export_timestamp": json.dumps(str(Path(project_dir))),
        "total_files": len(manifest_entries),
        "manifest": manifest_entries,
    }

    if fmt == "json":
        json_out = out_file if out_file.endswith(".json") else f"{out_file}.json"
        with open(json_out, "w", encoding="utf-8") as jf:
            json.dump(manifest_data, jf, indent=2)
        console.print(f"[bold green]✓ Manifesto JSON salvo com sucesso em {json_out}[/bold green]")
        return

    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for full_p, rel_p in files_to_pack:
            zf.write(full_p, arcname=str(rel_p))

        # Adiciona manifesto de auditoria assinado
        zf.writestr("audit_manifest.json", json.dumps(manifest_data, indent=2))

    console.print(f"[bold green]✓ Pacote de auditoria zip exportado com sucesso para {out_file} ({len(files_to_pack)} arquivos)[/bold green]")
