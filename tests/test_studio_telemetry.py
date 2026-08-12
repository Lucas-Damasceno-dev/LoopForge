"""Testes do comando 'lf studio' como visualizador de telemetria real."""

from __future__ import annotations

import sqlite3

from click.testing import CliRunner

from lf.cli.commands.studio import studio_cmd


def _run_studio(db_path: str, duration: int = 1):
    runner = CliRunner()
    return runner.invoke(studio_cmd, ["--duration", str(duration), "--db-path", db_path])


def test_studio_sem_db_mostra_mensagem_sem_dados_fake(tmp_path):
    res = _run_studio(str(tmp_path / "nao_existe.sqlite"))
    assert res.exit_code == 0
    assert "nenhuma execução encontrada" in res.output
    # Nenhum log fake hardcoded de orquestração.
    assert "Conectando ao orquestrador" not in res.output


def test_studio_lê_pipeline_runs(tmp_path):
    db_file = tmp_path / "telemetry.sqlite"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE pipeline_runs("
        "id TEXT, idea TEXT, stack TEXT, status TEXT, current_node TEXT, "
        "duration_seconds REAL, created_at TEXT)"
    )
    cur.execute(
        "INSERT INTO pipeline_runs VALUES "
        "('run-abc-1', 'API REST FastAPI', 'python', 'done', 'qa', 12.5, '2026-01-01 10:00:00')"
    )
    conn.commit()
    conn.close()

    res = _run_studio(str(db_file))
    assert res.exit_code == 0
    assert "API REST FastAPI" in res.output
    assert "DONE" in res.output


def test_studio_fallback_tabela_runs_do_telemetry_store(tmp_path):
    db_file = tmp_path / "telemetry.sqlite"
    conn = sqlite3.connect(db_file)
    conn.execute(
        "CREATE TABLE runs("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, task_id TEXT NOT NULL, "
        "node TEXT NOT NULL, status TEXT NOT NULL, duration_seconds REAL DEFAULT 0.0, "
        "cost_usd REAL DEFAULT 0.0, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO runs (session_id, task_id, node, status, duration_seconds, cost_usd) "
        "VALUES ('s1', 't1', 'developer', 'done', 3.2, 0.01)"
    )
    conn.commit()
    conn.close()

    res = _run_studio(str(db_file))
    assert res.exit_code == 0
    assert "DONE" in res.output
    assert "developer" in res.output


def test_studio_footer_mostra_so_atalhos_funcionais(tmp_path):
    res = _run_studio(str(tmp_path / "nao_existe.sqlite"))
    assert res.exit_code == 0
    assert "[R] Refresh" in res.output
    assert "[Q] Sair" in res.output
    # Atalhos mortos (E/S sem EventBus) foram removidos do footer.
    assert "Export" not in res.output
