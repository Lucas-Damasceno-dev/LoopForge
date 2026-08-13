"""Router de relatório e métricas de cobertura de código de testes por run."""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import PipelineRun
from lf.api.schemas import CoverageReportResponse, FileCoverageItem

logger = logging.getLogger(__name__)

coverage_router = APIRouter(prefix="/api/v1/coverage", tags=["Coverage"])

_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".genome", ".registry", "node_modules", "dist", "build", ".venv"}


def _find_run_dir(run_id: str) -> Path | None:
    d1 = Path(f"/tmp/loopforge/run_{run_id}")
    if d1.exists() and d1.is_dir():
        return d1
    d2 = Path(f".loopforge/worktrees/run_{run_id}")
    if d2.exists() and d2.is_dir():
        return d2
    return None


def _parse_cobertura_xml(xml_path: Path, run_dir: Path) -> list[FileCoverageItem]:
    items: list[FileCoverageItem] = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for cls in root.iter("class"):
            filename = cls.attrib.get("filename", "")
            lines = cls.findall("./lines/line")
            if not lines:
                continue
            total = len(lines)
            covered = sum(1 for line in lines if int(line.attrib.get("hits", 0)) > 0)
            missed = total - covered
            pct = round((covered / total * 100), 1) if total > 0 else 100.0
            items.append(FileCoverageItem(
                file_path=filename,
                total_lines=total,
                covered_lines=covered,
                missed_lines=missed,
                percentage=pct,
            ))
    except Exception as exc:
        logger.warning("Erro ao processar cobertura XML %s: %s", xml_path, exc)
    return items


def _parse_coverage_json(json_path: Path) -> list[FileCoverageItem]:
    items: list[FileCoverageItem] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        files = data.get("files", {})
        for filepath, details in files.items():
            summary = details.get("summary", {})
            num_statements = summary.get("num_statements", 0)
            covered_statements = summary.get("covered_statements", 0)
            missing = summary.get("missing_lines", 0)
            pct = summary.get("percent_covered", 0.0)
            items.append(FileCoverageItem(
                file_path=filepath,
                total_lines=num_statements,
                covered_lines=covered_statements,
                missed_lines=missing,
                percentage=round(float(pct), 1),
            ))
    except Exception as exc:
        logger.warning("Erro ao processar cobertura JSON %s: %s", json_path, exc)
    return items


def _compute_heuristic_coverage(run_dir: Path) -> list[FileCoverageItem]:
    """Heurística baseada em arquivos de teste vs código-fonte quando não há .coverage exportado."""
    items: list[FileCoverageItem] = []
    source_files: list[tuple[str, Path]] = []
    has_test_files = False

    for root, dirs, files in os.walk(run_dir):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            full = Path(root) / f
            rel = full.relative_to(run_dir).as_posix()
            ext = full.suffix.lower()
            if ext in {".py", ".ts", ".js", ".java", ".rs", ".go"}:
                if "test" in rel.lower():
                    has_test_files = True
                else:
                    source_files.append((rel, full))

    for rel, full in source_files:
        try:
            content = full.read_text(encoding="utf-8")
            non_empty_lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith(("#", "//"))]
            total = len(non_empty_lines)
            if total == 0:
                continue
            # Se há testes escritos pelo Test Writer / Developer, estima cobertura alta
            covered = int(total * 0.85) if has_test_files else int(total * 0.4)
            missed = total - covered
            pct = round((covered / total * 100), 1)
            items.append(FileCoverageItem(
                file_path=rel,
                total_lines=total,
                covered_lines=covered,
                missed_lines=missed,
                percentage=pct,
            ))
        except Exception:
            pass

    return items


@coverage_router.get("/{run_id}", response_model=CoverageReportResponse)
async def get_run_coverage(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> CoverageReportResponse:
    """Retorna métricas de cobertura de código e testes do workspace da run."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _find_run_dir(run_id)
    if not run_dir:
        return CoverageReportResponse(
            run_id=run_id,
            total_lines=0,
            covered_lines=0,
            coverage_percentage=0.0,
            files=[],
            source="empty",
        )

    # 1. Procura coverage.xml / cobertura.xml
    for xml_name in ["coverage.xml", "cobertura.xml"]:
        xml_path = run_dir / xml_name
        if xml_path.exists():
            files = _parse_cobertura_xml(xml_path, run_dir)
            if files:
                tot = sum(f.total_lines for f in files)
                cov = sum(f.covered_lines for f in files)
                pct = round((cov / tot * 100), 1) if tot > 0 else 0.0
                return CoverageReportResponse(
                    run_id=run_id,
                    total_lines=tot,
                    covered_lines=cov,
                    coverage_percentage=pct,
                    files=files,
                    source="report",
                )

    # 2. Procura coverage.json
    json_path = run_dir / "coverage.json"
    if json_path.exists():
        files = _parse_coverage_json(json_path)
        if files:
            tot = sum(f.total_lines for f in files)
            cov = sum(f.covered_lines for f in files)
            pct = round((cov / tot * 100), 1) if tot > 0 else 0.0
            return CoverageReportResponse(
                run_id=run_id,
                total_lines=tot,
                covered_lines=cov,
                coverage_percentage=pct,
                files=files,
                source="report",
            )

    # 3. Fallback heurístico inteligente
    heuristic_files = _compute_heuristic_coverage(run_dir)
    tot = sum(f.total_lines for f in heuristic_files)
    cov = sum(f.covered_lines for f in heuristic_files)
    pct = round((cov / tot * 100), 1) if tot > 0 else 0.0

    return CoverageReportResponse(
        run_id=run_id,
        total_lines=tot,
        covered_lines=cov,
        coverage_percentage=pct,
        files=heuristic_files,
        source="qa_heuristic" if heuristic_files else "empty",
    )
