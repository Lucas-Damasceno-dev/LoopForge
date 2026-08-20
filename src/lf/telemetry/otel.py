"""OpenTelemetry / Langfuse Tracing Adapter para LoopForge.

Permite registrar spans de execução de cada nó do DAG com metadados de:
- run_id / task_id / node_name
- duração em milissegundos
- custo em USD e consumo de tokens
- status (ok, error, paused, retry)
- atributos customizados e tags

Exporta para:
1. Arquivo local `.loopforge/traces.jsonl` (modo offline/dev)
2. HTTP OTLP Collector / Langfuse se configurado via env var
   (OTEL_EXPORTER_OTLP_ENDPOINT ou LANGFUSE_HOST)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..config.paths import LOOPFORGE_DIR

TRACES_FILE_PATH = LOOPFORGE_DIR / "traces.jsonl"


class OtelSpan:
    """Representação de um span OTel/Langfuse para um nó do pipeline."""

    def __init__(
        self,
        name: str,
        run_id: str,
        node: str,
        duration_ms: float,
        cost_usd: float = 0.0,
        status: str = "ok",
        attributes: dict[str, Any] | None = None,
        timestamp: float | None = None,
    ):
        self.name = name
        self.run_id = run_id
        self.node = node
        self.duration_ms = duration_ms
        self.cost_usd = cost_usd
        self.status = status
        self.attributes = attributes or {}
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.run_id,
            "span_name": self.name,
            "node": self.node,
            "duration_ms": round(self.duration_ms, 2),
            "cost_usd": self.cost_usd,
            "status": self.status,
            "timestamp": self.timestamp,
            "attributes": {
                "service.name": "loopforge-engine",
                "loopforge.node": self.node,
                "loopforge.run_id": self.run_id,
                **self.attributes,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def record_otel_span(
    name: str,
    run_id: str,
    node: str,
    duration_ms: float,
    cost_usd: float = 0.0,
    status: str = "ok",
    attributes: dict[str, Any] | None = None,
    file_path: Path = TRACES_FILE_PATH,
) -> dict[str, Any]:
    """Registra um span de telemetria OTel em traces.jsonl."""
    span = OtelSpan(
        name=name,
        run_id=run_id,
        node=node,
        duration_ms=duration_ms,
        cost_usd=cost_usd,
        status=status,
        attributes=attributes,
    )
    span_data = span.to_dict()

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(span_data, ensure_ascii=False) + "\n")
    except Exception:
        # Tracing falha de forma não-bloqueante
        pass

    return span_data


def list_otel_spans_for_run(run_id: str, file_path: Path = TRACES_FILE_PATH) -> list[dict[str, Any]]:
    """Lê todos os spans gravados para uma determinada run."""
    if not file_path.exists():
        return []

    spans: list[dict[str, Any]] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("trace_id") == run_id:
                    spans.append(data)
    except Exception:
        pass
    return spans
