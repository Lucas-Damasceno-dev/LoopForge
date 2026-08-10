import os
import subprocess
from dataclasses import dataclass, field
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
    command: str = ""
    # True quando o comando de teste não foi encontrado no PATH (ex.: pytest
    # fora do venv). O QA usa isso para diferenciar "nenhum teste" real de
    # "não há harness instalado" — evita o relatório enganoso de 0 testes.
    command_missing: bool = False
    # Módulos que falharam na coleta do pytest (ex.: ImportError). O QA usa
    # para reportar a causa real em vez do genérico "nenhum teste executado".
    errors: list[str] = field(default_factory=list)


def _find_venv_bin(cwd: str | Path) -> Path | None:
    """Procura .venv/bin (ou venv/bin) em cwd e até 3 níveis de pai."""
    current = Path(cwd).resolve()
    for _ in range(4):  # cwd + 3 pais
        for name in (".venv", "venv"):
            candidate = current / name / "bin"
            if candidate.is_dir():
                return candidate
        current = current.parent
    return None


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
        # Timeout configurável via LF_TEST_TIMEOUT (segundos). Vazio/0 = sem timeout.
        timeout: int | None = None
        raw_timeout = os.environ.get("LF_TEST_TIMEOUT")
        if raw_timeout:
            try:
                parsed = int(raw_timeout)
                if parsed > 0:
                    timeout = parsed
            except ValueError:
                pass
        try:
            env = os.environ.copy()
            venv_bin = _find_venv_bin(cwd)
            if venv_bin is not None:
                env["PATH"] = str(venv_bin) + os.pathsep + env["PATH"]
            if self.stack and "python" in self.stack.lower():
                # Testes do projeto importam `lf...` do src gerado: expõe o src
                # no PYTHONPATH além do cwd do projeto testado.
                cwd_path = Path(cwd).resolve()
                env["PYTHONPATH"] = os.pathsep.join(
                    filter(None, [env.get("PYTHONPATH", ""), str(cwd_path), str(cwd_path / "src")])
                )
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            parsed = parse_test_output(res.stdout + "\n" + res.stderr)
            # Erro de coleta (pytest retorna exit code != 0) também invalida o run,
            # mesmo que o shell não sinalize falha — defensivo.
            success = res.returncode == 0 and not parsed["errors"]
            stderr_text = res.stderr or ""
            # Comando não encontrado: o shell retorna 127 (ou "not recognized"
            # no Windows). NÃO tratar como "0 testes coletados" — preserva o
            # stderr original e sinaliza command_missing para o QA reportar a
            # causa real (venv/harness não instalado).
            command_missing = (
                res.returncode == 127
                or "command not found" in stderr_text.lower()
                or "no such file or directory" in stderr_text.lower()
                or "not recognized" in stderr_text.lower()
            )
            return TestHarnessResult(
                total=parsed["total"],
                passed=parsed["passed"],
                failed=parsed["failed"],
                output=res.stdout + "\n" + res.stderr,
                success=success,
                command=cmd,
                command_missing=command_missing,
                errors=parsed["errors"],
            )
        except Exception as exc:
            return TestHarnessResult(
                total=1,
                passed=0,
                failed=1,
                output=str(exc),
                success=False,
                command=cmd,
                errors=[],
            )
