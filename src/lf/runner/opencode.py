from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import time


@dataclass
class OpenCodeResult:
    exit_code: int
    stdout: str
    stderr: str
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""
    duration_seconds: float = 0.0


class OpenCodeRunner:
    def __init__(self, timeout_seconds: int = 300):
        self.timeout = timeout_seconds

    def run(self, prompt: str, project_root: str | Path = ".") -> OpenCodeResult:
        root = Path(project_root).resolve()
        start_time = time.time()

        # Check mock mode or missing binary
        is_mock = os.environ.get("OPENCODE_MOCK", "0") == "1" or not shutil.which("opencode")

        if is_mock:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=0,
                stdout=f"[MOCK OPENCODE] Executed prompt: {prompt[:80]}...",
                stderr="",
                changed_files=[],
                diff="[Mock diff: 0 files changed]",
                duration_seconds=duration,
            )

        cmd = ["opencode", "run", "--prompt", prompt, "--path", str(root)]

        try:
            res = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=os.environ.copy(),
            )
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                changed_files=[],
                diff="",
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=f"OpenCode execution timed out after {self.timeout}s",
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=1,
                stdout="",
                stderr=str(exc),
                duration_seconds=duration,
            )
