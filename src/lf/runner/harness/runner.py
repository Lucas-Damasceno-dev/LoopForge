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

    def __init__(self, command: str | None = None, stack: str | None = None):
        self.command = command
        self.stack = stack

    def _detect_command(self, cwd: str | Path) -> str:
        if self.command:
            return self.command

        cwd_path = Path(cwd)

        # 1. Stack explícita ou detectada por manifesto
        if self.stack == "go" or (cwd_path / "go.mod").exists():
            return "go test ./..."

        if self.stack == "rust" or (cwd_path / "Cargo.toml").exists():
            return "cargo test"

        if self.stack == "java" or (cwd_path / "pom.xml").exists() or (cwd_path / "build.gradle").exists() or (cwd_path / "build.gradle.kts").exists():
            if (cwd_path / "pom.xml").exists():
                return "mvn test"
            if (cwd_path / "gradlew").exists():
                return "./gradlew test"
            return "gradle test"

        if self.stack in ("javascript", "typescript") or (cwd_path / "package.json").exists():
            if (cwd_path / "vitest.config.ts").exists() or (cwd_path / "vitest.config.js").exists():
                return "npx vitest run"
            if (cwd_path / "jest.config.js").exists() or (cwd_path / "jest.config.ts").exists():
                return "npx jest"
            return "npm test"

        return "pytest"

    def run(self, cwd: str | Path = ".") -> TestHarnessResult:
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
