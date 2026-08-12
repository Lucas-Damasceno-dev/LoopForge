"""Fix: timeout do OpenCodeRunner mata a ÁRVORE de processos, não só o `script`.

Reproduz a falha real: com subprocess.run, o timeout matava apenas o líder
(`script`); os filhos (sh → opencode → agentes) ficavam órfãos. O runner agora
mata o grupo do `script` (killpg) + descendentes via /proc (a árvore opencode
vive em sessão própria, criada pelo forkpty/setsid do `script`). O teste usa um
binário `opencode` FAKE (script bash real) que grava o próprio PID e dorme,
exercitando o caminho REAL do runner (script + Popen + start_new_session +
killpg + descendants no TimeoutExpired) — nada do mecanismo de kill é mockado.
"""

import os
import stat
import time
from pathlib import Path

import pytest

from lf.runner.opencode.models import OpenCodeResult
from lf.runner.opencode.runner import OpenCodeRunner


def _make_fake_opencode(tmp_path: Path) -> tuple[Path, Path]:
    """Cria binário `opencode` fake: grava o próprio PID e dorme 60s.

    `exec sleep 60` preserva o PID do fake — o PID gravado é o do processo que
    vira o filho, então checar `os.kill(pid, 0)` prova que o filho morreu.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    pidfile = tmp_path / "opencode_child.pid"
    bin_path = bin_dir / "opencode"
    if not bin_path.exists():
        bin_path.write_text(f"#!/bin/bash\necho $$ > {pidfile}\nexec sleep 60\n")
        bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_path, pidfile


def _child_alive(pidfile: Path) -> bool:
    """True se o processo (filho do fake opencode) ainda existe."""
    try:
        pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        return True  # pidfile ausente/vazio → não dá pra provar morto
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_child_dead(pidfile: Path, timeout: float = 5.0) -> bool:
    """Espera (com poll) o filho morrer; entrega de SIGKILL é assíncrona."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _child_alive(pidfile):
            return True
        time.sleep(0.05)
    return not _child_alive(pidfile)


def _run_with_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: int) -> tuple[OpenCodeResult, Path]:
    """Sobe o runner com o opencode fake no PATH e executa até o timeout."""
    bin_path, pidfile = _make_fake_opencode(tmp_path)
    run_root = tmp_path / f"run_{timeout}_{int(time.time() * 1000)}"
    run_root.mkdir()
    monkeypatch.setenv("PATH", f"{bin_path.parent}:{os.environ['PATH']}")
    monkeypatch.setenv("OPENCODE_MOCK", "0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENCODE_MODEL", "oc/deepseek-v4-flash-free")

    runner = OpenCodeRunner(timeout_seconds=timeout)
    res = runner.run(prompt="teste killpg", project_root=str(run_root))

    # Espera o pidfile ser gravado (spawn + echo) — loop curto p/ CI lento
    deadline = time.time() + 5
    while not pidfile.exists() and time.time() < deadline:
        time.sleep(0.05)
    return res, pidfile


def test_timeout_kills_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Após o timeout, o processo filho (sleep) não pode continuar vivo."""
    res, pidfile = _run_with_timeout(tmp_path, monkeypatch, timeout=3)

    assert res.exit_code == 124
    assert "timed out" in res.stderr
    assert pidfile.exists(), "fake opencode não chegou a gravar o pidfile"
    assert _wait_child_dead(pidfile), "processo filho ficou órfão após o timeout"


def test_timeout_killpg_stability_3x(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Estabilidade: killpg funcionando em 3 execuções seguidas (sem órfãos)."""
    for i in range(3):
        res, pidfile = _run_with_timeout(tmp_path, monkeypatch, timeout=2)
        assert res.exit_code == 124
        assert pidfile.exists(), f"iteração {i}: pidfile não gravado"
        assert _wait_child_dead(pidfile), f"iteração {i}: filho órfão sobreviveu"
