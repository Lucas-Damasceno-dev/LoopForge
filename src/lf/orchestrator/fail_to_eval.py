"""FailToEval: Gerador de Benchmarks Nativos de Regressão a partir de Falhas do Agente."""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional


class FailToEval:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.benchmarks_dir = os.path.join(self.repo_root, ".loopforge", "benchmarks")
        os.makedirs(self.benchmarks_dir, exist_ok=True)

    def create_benchmark_case(
        self,
        task_id: str,
        prompt: str,
        initial_files: Dict[str, str],
        expected_patch_files: Dict[str, str],
        failure_reason: str = "QA Failure / Human Interrupt",
    ) -> str:
        now_iso = datetime.now(timezone.utc).isoformat()
        benchmark_id = f"bench_{task_id}_{int(datetime.now().timestamp())}"

        data = {
            "benchmark_id": benchmark_id,
            "created_at": now_iso,
            "task_id": task_id,
            "prompt": prompt,
            "failure_reason": failure_reason,
            "initial_files": initial_files,
            "expected_patch_files": expected_patch_files,
        }

        output_path = os.path.join(self.benchmarks_dir, f"{benchmark_id}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"--- INFO: FailToEval gerou novo benchmark de regressão em {output_path} ---")
        return output_path
