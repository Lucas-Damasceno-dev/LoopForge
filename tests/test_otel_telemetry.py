"""Testes para o adaptador de telemetria OpenTelemetry / Langfuse (otel.py)."""

import json
from pathlib import Path
import pytest
from lf.telemetry.otel import OtelSpan, record_otel_span, list_otel_spans_for_run


def test_otel_span_structure():
    span = OtelSpan(
        name="execute_cpo",
        run_id="run-123",
        node="cpo",
        duration_ms=150.5,
        cost_usd=0.002,
        status="ok",
        attributes={"model": "gpt-4o"},
    )
    data = span.to_dict()
    assert data["trace_id"] == "run-123"
    assert data["span_name"] == "execute_cpo"
    assert data["node"] == "cpo"
    assert data["duration_ms"] == 150.5
    assert data["cost_usd"] == 0.002
    assert data["status"] == "ok"
    assert data["attributes"]["service.name"] == "loopforge-engine"
    assert data["attributes"]["model"] == "gpt-4o"


def test_record_and_list_otel_spans(tmp_path: Path):
    trace_file = tmp_path / "traces.jsonl"
    span_data = record_otel_span(
        name="execute_developer",
        run_id="run-abc",
        node="developer",
        duration_ms=500.0,
        cost_usd=0.015,
        status="ok",
        file_path=trace_file,
    )
    assert span_data["span_name"] == "execute_developer"
    assert trace_file.exists()

    # Registra outro span para mesma run e para outra run
    record_otel_span(
        name="execute_qa",
        run_id="run-abc",
        node="qa",
        duration_ms=250.0,
        cost_usd=0.005,
        status="ok",
        file_path=trace_file,
    )
    record_otel_span(
        name="execute_cpo",
        run_id="run-other",
        node="cpo",
        duration_ms=100.0,
        cost_usd=0.001,
        status="ok",
        file_path=trace_file,
    )

    spans = list_otel_spans_for_run("run-abc", file_path=trace_file)
    assert len(spans) == 2
    assert [s["node"] for s in spans] == ["developer", "qa"]
