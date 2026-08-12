"""Testes do benchmark real: custo via telemetry, cache hit rate e artefatos exportados."""

import json

from click.testing import CliRunner

from lf.cli.commands.benchmark import benchmark_cmd
from lf.pipeline.cache import SQLiteLLMCache
from lf.pipeline.llm_factory import CostTracker
from lf.telemetry.costs import (
    query_llm_costs_since,
    query_node_costs_since,
    snapshot_llm_cost_watermark,
)


def test_cache_stats_hit_miss_and_clear(tmp_path):
    cache = SQLiteLLMCache(tmp_path / "cache.sqlite")
    assert cache.stats()["total"] == 0

    cache.set("prompt-1", "resp-1")
    assert cache.get("prompt-1") == "resp-1"
    assert cache.get("prompt-1") == "resp-1"
    assert cache.get("prompt-miss") is None

    stats = cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["total"] == 3
    assert round(stats["hit_rate"], 2) == round(2 / 3, 2)

    cache.clear()
    assert cache.stats()["total"] == 0


def test_cost_watermark_isolates_runs(tmp_path):
    db = tmp_path / "telemetry.sqlite"
    tracker = CostTracker(db_path=db)

    # Sem dados prévios: watermark None (nada medido antes)
    assert snapshot_llm_cost_watermark(db) is None

    tracker.track(model="openai/gpt-4o-mini", prompt_text="a" * 100, response_text="b" * 100)
    wm = snapshot_llm_cost_watermark(db)
    assert wm == 1

    # Segunda chamada com node — deve aparecer SOMENTE no query "since wm"
    tracker.track(
        model="openai/gpt-4o-mini",
        prompt_text="c" * 100,
        response_text="d" * 100,
        node="cpo",
    )
    after = query_llm_costs_since(wm, db)
    assert after["available"] is True
    assert after["rows"] == 1
    assert after["total_cost_usd"] > 0.0
    assert after["models"] == ["openai/gpt-4o-mini"]

    node_costs = query_node_costs_since(wm, db)
    assert node_costs.get("cpo", 0.0) > 0.0

    # watermark None (sem dados na captura) conta todas as linhas
    all_costs = query_llm_costs_since(None, db)
    assert all_costs["rows"] == 2
    assert all_costs["available"] is True


def test_cost_not_available_without_db(tmp_path):
    missing = tmp_path / "nao_existe.sqlite"
    assert snapshot_llm_cost_watermark(missing) is None
    info = query_llm_costs_since(None, missing)
    assert info["available"] is False


def test_benchmark_mock_artifact_schema(tmp_path):
    runner = CliRunner()
    storage = str(tmp_path / "benchmarks")
    res = runner.invoke(benchmark_cmd, ["--limit", "1", "--runs", "2", "--mock", "--storage-dir", storage])
    assert res.exit_code == 0, res.output
    assert "LoopForge" in res.output
    assert "Artefatos" in res.output

    results_path = tmp_path / "benchmarks" / "results.json"
    report_path = tmp_path / "benchmarks" / "benchmark_report.md"
    assert results_path.exists()
    assert report_path.exists()

    data = json.loads(results_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["mock"] is True
    assert data["runs"] == 2
    assert data["model"] == "mock"
    assert "elo" in data and "per_problem" in data and "per_stack" in data

    pid = list(data["per_problem"])[0]
    assert data["per_problem"][pid]["runs"] == 2
    assert len(data["per_problem"][pid]["records"]) == 2
    assert data["per_problem"][pid]["records"][0]["run"] == 1
    assert data["per_problem"][pid]["records"][1]["run"] == 2
    assert "loopforge benchmark report" in report_path.read_text(encoding="utf-8").lower()
