import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .parser import parse_test_output


@dataclass
class TestHarnessResult:
    __test__ = False
    total: int
    passed: int
    failed: int
    output: str
    success: bool


class TestHarnessRunner:
    """Multi-stack Test Harness (pytest, vitest, jest, go test, cargo test, maven, gradle)."""

    __test__ = False

    def __init__(self, command: str | None = None, stack: str | None = None, auto_format: bool = False):
        self.command = command
        self.stack = stack
        self.auto_format = auto_format

    def _detect_command(self, cwd: str | Path) -> str:
        if self.command:
            return self.command

        from ...config.registry import TechStackRegistry

        cwd_str = str(cwd)
        if self.stack:
            handler = TechStackRegistry.get(self.stack)
            if handler:
                return handler.detect_test_command(cwd_str) or handler.get_fallback_test_command()

        cmd = TechStackRegistry.detect_command(cwd_str)
        if cmd:
            return cmd

        return "pytest"

    def run_auto_formatter(self, cwd: str | Path = ".") -> None:
        """Executa auto-formatador nativo da linguagem (cargo fmt, ruff format, gofmt) antes dos testes."""
        import shutil
        cmd = self._detect_command(cwd)
        try:
            if "cargo" in cmd and shutil.which("cargo"):
                subprocess.run("cargo fmt", shell=True, cwd=cwd, capture_output=True, timeout=30)
            elif "pytest" in cmd and shutil.which("ruff"):
                subprocess.run("ruff format .", shell=True, cwd=cwd, capture_output=True, timeout=30)
            elif "go" in cmd and shutil.which("gofmt"):
                subprocess.run("gofmt -w .", shell=True, cwd=cwd, capture_output=True, timeout=30)
            elif ("npm" in cmd or "npx" in cmd or "vitest" in cmd) and shutil.which("npx"):
                subprocess.run("npx prettier --write .", shell=True, cwd=cwd, capture_output=True, timeout=30)
        except Exception as exc:
            print(f"--- AVISO: Falha na execução do auto-formatador: {exc} ---")

    def run(self, cwd: str | Path = ".") -> TestHarnessResult:
        if self.auto_format:
            self.run_auto_formatter(cwd)
        cmd = self._detect_command(cwd)
        try:
            res = subprocess.run(
                cmd,
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
