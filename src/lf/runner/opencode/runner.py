import os
import shutil
import subprocess
import time
from pathlib import Path

from .models import OpenCodeResult

DEFAULT_OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL") or os.environ.get("OPENROUTER_MODEL") or "auto/best-free"


class OpenCodeRunner:
    """Gerencia execução de instâncias OpenCode via subprocesso."""

    def __init__(self, timeout_seconds: int = 600):
        self.timeout = timeout_seconds

    def run(
        self,
        prompt: str,
        project_root: str | Path = ".",
        model: str | None = None,
        circuit_breaker=None,
    ) -> OpenCodeResult:
        """Executa OpenCode com verificação opcional de circuit breaker."""
        # Verifica circuit breaker antes de spawnar subprocesso
        if circuit_breaker is not None and not circuit_breaker.can_proceed():
            return OpenCodeResult(
                exit_code=1,
                stdout="",
                stderr="Circuit breaker is open - cannot proceed",
                duration_seconds=0.0,
            )

        model_to_use = model or os.environ.get("OPENCODE_MODEL", DEFAULT_OPENCODE_MODEL)
        root = Path(project_root).resolve()
        start_time = time.time()

        is_mock = os.environ.get("OPENCODE_MOCK", "0") == "1" or not shutil.which("opencode")

        if is_mock:
            duration = time.time() - start_time
            return OpenCodeResult(
                exit_code=0,
                stdout=f"[MOCK OPENCODE] Executed prompt: {prompt[:120]}...",
                stderr="",
                changed_files=[],
                diff="[Mock diff: 0 files changed]",
                duration_seconds=duration,
            )

        # opencode run requer TTY; envolvemos com script (pseudoterminal)
        safe_prompt = prompt.replace("'", "'\\''")
        cmd = [
            "script", "-q", "-c",
            f"opencode run '{safe_prompt}' -m {model_to_use} --pure",
            "/dev/null"
        ]

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
            changed_files = detect_changed_files(root, start_time)
            return OpenCodeResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                changed_files=changed_files,
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


def detect_changed_files(project_root: str | Path, start_time: float) -> list[str]:
    """Detecta arquivos criados ou modificados no project_root após start_time."""
    root = Path(project_root).resolve()
    ignored_parts = {
        ".git", ".loopforge", "__pycache__", ".pytest_cache", "node_modules",
        "venv", ".venv", ".mypy_cache", ".gemini"
    }
    ignored_files = {
        "generated_code.py", ".loopforge.json", "llm_cache.sqlite", ".users.json", "loop.lock"
    }

    changed: list[str] = []

    # 1. Tenta git status se for um repositório git
    git_dir = root / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2:
                        rel_path = parts[1].strip('"')
                        file_path = root / rel_path
                        if any(part in ignored_parts for part in file_path.parts):
                            continue
                        if file_path.name in ignored_files or file_path.name.startswith("test_report_"):
                            continue
                        if file_path.is_file():
                            changed.append(str(file_path))
        except Exception as e:
            print(f"--- AVISO: Erro ao detectar mudanças (git diff): {e} ---")

    # 2. Fallback: verificação de mtime
    if not changed and root.exists():
        try:
            for p in root.rglob("*"):
                if p.is_file():
                    if any(part in ignored_parts for part in p.parts):
                        continue
                    if p.name in ignored_files or p.name.startswith("test_report_"):
                        continue
                    try:
                        if p.stat().st_mtime >= start_time - 1.0:
                            changed.append(str(p))
                    except OSError:
                        pass
        except Exception as e:
            print(f"--- AVISO: Erro ao detectar mudanças (mtime fallback): {e} ---")

    return changed
