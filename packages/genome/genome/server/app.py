"""Servidor HTTP REST (FastAPI) para genome serve."""

from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from genome.core.renderers import render_json, render_markdown, render_summary
from genome.core.scanner import GenomeScanner
from genome.store.sqlite import GenomeStore

def create_genome_app(repo_root: str = ".") -> FastAPI:
    app = FastAPI(title="Codebase Genome API", version="1.0.0")

    @app.get("/genome")
    def get_genome(format: str = Query("json", regex="^(json|markdown|summary)$")):
        store = GenomeStore(repo_root)
        genome = store.load_genome()
        if not genome:
            scanner = GenomeScanner(repo_root)
            genome = scanner.scan()

        if format == "markdown":
            return {"content": render_markdown(genome)}
        elif format == "summary":
            return {"content": render_summary(genome)}
        else:
            return genome.model_dump()

    @app.get("/check")
    def check_file(file: str):
        store = GenomeStore(repo_root)
        genome = store.load_genome()
        if not genome:
            scanner = GenomeScanner(repo_root)
            genome = scanner.scan()

        target_mod = next((m for m in genome.modules if m.path == file), None)
        if not target_mod:
            raise HTTPException(status_code=404, detail=f"Arquivo '{file}' não encontrado no genoma.")

        violations = [v for v in genome.architecture.layer_violations if v.from_path == file]
        is_bus_risk = any(hrf.path == file for hrf in genome.architecture.bus_factor.high_risk_files)

        return {
            "file": file,
            "instability": target_mod.instability,
            "exports_count": len(target_mod.exports),
            "dependents_count": len(target_mod.dependents),
            "layer_violations": violations,
            "is_high_risk_bus_factor": is_bus_risk,
        }

    return app
