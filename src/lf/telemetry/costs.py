"""Consulta de custos reais de LLM persistidos em ``.loopforge/telemetry.sqlite``.

O ``CostTracker`` (src/lf/pipeline/llm_factory.py) registra uma linha em
``llm_costs`` a cada chamada LLM real. O padrão de leitura aqui é idempotente
por watermark: captura ``MAX(id)`` antes da execução e consulta apenas as
linhas com ``id > watermark`` — isola o custo da run atual de execuções
anteriores sem precisar de ``run_id`` no schema.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config.paths import TELEMETRY_DB_PATH


def _connect(db_path: str | Path = TELEMETRY_DB_PATH) -> sqlite3.Connection | None:
    """Abre conexão com o telemetry DB. Retorna None se o arquivo não existe."""
    path = Path(db_path)
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    except Exception:
        return None


def _has_llm_costs_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'llm_costs'").fetchone()
    return row is not None


def snapshot_llm_cost_watermark(db_path: str | Path = TELEMETRY_DB_PATH) -> int | None:
    """Retorna ``MAX(id)`` de ``llm_costs`` (watermark) antes da execução.

    Retorna None quando não há dados prévios (tabela ausente ou vazia) — nesse
    caso o "antes" é o início de tudo e a consulta posterior conta todas as
    linhas (``id > -1``).
    """
    conn = _connect(db_path)
    if conn is None:
        return None
    try:
        with conn:
            if not _has_llm_costs_table(conn):
                return None
            row = conn.execute("SELECT MAX(id) FROM llm_costs").fetchone()
            return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None
    finally:
        conn.close()


def query_llm_costs_since(watermark: int | None, db_path: str | Path = TELEMETRY_DB_PATH) -> dict[str, Any]:
    """Custo agregado e modelos reais das chamadas LLM desde o watermark.

    Retorna: ``{available, total_cost_usd, models, rows}``. ``available=False``
    significa que não foi possível medir (DB/tabela ausente) — o caller deve
    reportar "n/a", nunca hardcode.
    """
    result: dict[str, Any] = {"available": False, "total_cost_usd": 0.0, "models": [], "rows": 0}
    conn = _connect(db_path)
    if conn is None:
        return result
    try:
        with conn:
            if not _has_llm_costs_table(conn):
                return result
            # watermark None => sem dados prévios: conta todas as linhas (id > -1)
            low = watermark if watermark is not None else -1
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) AS total, COUNT(*) AS n FROM llm_costs WHERE id > ?",
                (low,),
            ).fetchone()
            total = float(row[0] or 0.0)
            n = int(row[1] or 0)
            models = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT model FROM llm_costs WHERE id > ? ORDER BY model", (low,)
                ).fetchall()
            ]
            result.update({"available": True, "total_cost_usd": total, "models": models, "rows": n})
            return result
    except Exception:
        return result
    finally:
        conn.close()


def query_node_costs_since(watermark: int | None, db_path: str | Path = TELEMETRY_DB_PATH) -> dict[str, float]:
    """Custo por nó do pipeline desde o watermark (coluna ``node`` de llm_costs)."""
    node_costs: dict[str, float] = {}
    conn = _connect(db_path)
    if conn is None:
        return node_costs
    try:
        with conn:
            if not _has_llm_costs_table(conn):
                return node_costs
            low = watermark if watermark is not None else -1
            for node, total in conn.execute(
                "SELECT node, COALESCE(SUM(cost_usd), 0.0) FROM llm_costs "
                "WHERE id > ? AND node IS NOT NULL GROUP BY node ORDER BY node",
                (low,),
            ).fetchall():
                node_costs[str(node)] = float(total)
    except Exception:
        pass
    finally:
        conn.close()
    return node_costs
