from dataclasses import dataclass
from pathlib import Path
import subprocess

from .parser import parse_test_output


@dataclass
class TestHarnessResult:
    total: int
    passed: int
    failed: int
    output: str
    success: bool


class TestHarnessRunner:
    def __init__(self, command: str = "pytest"):
        self.command = command

    def run(self, cwd: str | Path = ".") -> TestHarnessResult:
        try:
            res = subprocess.run(
                self.command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            parsed = parse_test_output(res.stdout + "\n" + res.stderr)
            success = res.returncode == 0
            return TestHarnessResult(
                total=parsed["total"],
                passed=parsed["passed"],
                failed=parsed["failed"],
                output=res.stdout + "\n" + res.stderr,
                success=success,
            )
        except Exception as exc:
            return TestHarnessResult(
                total=1,
                passed=0,
                failed=1,
                output=str(exc),
                success=False,
            )
