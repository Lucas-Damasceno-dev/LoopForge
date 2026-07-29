"""Benchmark Suite: Métricas de sucesso por stack, custo por run e tempo por nó."""
from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class NodeBenchmark:
    node_name: str
    duration_seconds: float
    status: str = "success"


@dataclass
class RunBenchmark:
    run_id: str
    stack: str
    idea: str
    total_duration_seconds: float
    estimated_cost_usd: float
    node_benchmarks: list[NodeBenchmark] = field(default_factory=list)
    success: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BenchmarkSuite:
    """Registra e calcula benchmarks de desempenho e custo do LoopForge."""

    def __init__(self, storage_dir: str = ".loopforge/benchmarks"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def record_run(self, benchmark: RunBenchmark) -> str:
        """Salva métrica de benchmark em disco."""
        path = os.path.join(self.storage_dir, f"run_{benchmark.run_id}.json")
        data = asdict(benchmark)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def get_summary(self) -> dict:
        """Gera resumo consolidado das métricas de benchmark por stack."""
        if not os.path.exists(self.storage_dir):
            return {"total_runs": 0, "by_stack": {}}

        files = [
            os.path.join(self.storage_dir, f)
            for f in os.listdir(self.storage_dir)
            if f.endswith(".json")
        ]

        if not files:
            return {"total_runs": 0, "by_stack": {}}

        total_runs = len(files)
        total_cost = 0.0
        by_stack: dict[str, dict] = {}

        for fpath in files:
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)

                stack = data.get("stack", "python")
                cost = data.get("estimated_cost_usd", 0.0)
                dur = data.get("total_duration_seconds", 0.0)
                success = data.get("success", True)

                total_cost += cost

                if stack not in by_stack:
                    by_stack[stack] = {
                        "runs": 0,
                        "successful": 0,
                        "total_duration": 0.0,
                        "total_cost": 0.0,
                    }

                by_stack[stack]["runs"] += 1
                if success:
                    by_stack[stack]["successful"] += 1
                by_stack[stack]["total_duration"] += dur
                by_stack[stack]["total_cost"] += cost
            except Exception:
                pass

        for s, metrics in by_stack.items():
            runs = metrics["runs"]
            metrics["success_rate"] = (metrics["successful"] / runs) * 100 if runs > 0 else 0.0
            metrics["avg_duration_seconds"] = metrics["total_duration"] / runs if runs > 0 else 0.0
            metrics["avg_cost_usd"] = metrics["total_cost"] / runs if runs > 0 else 0.0

        return {
            "total_runs": total_runs,
            "total_cost_usd": total_cost,
            "by_stack": by_stack,
        }
