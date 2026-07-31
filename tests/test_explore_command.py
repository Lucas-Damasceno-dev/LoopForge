"""Testes de cobertura para o comando lf explore."""

from __future__ import annotations

import sqlite3

from rich.console import Console

from lf.cli.commands import explore as explore_module


def _run_explore(db_path: str):
    explore_module.explore_cmd.callback(db_path=db_path)  # type: ignore[attr-defined]


def test_db_inexistente_mostra_mensagem_amarela(monkeypatch, tmp_path):
    monkeypatch.setattr(explore_module, "console", Console(record=True))
    _run_explore(str(tmp_path / "nao_existe.sqlite"))
    assert "Nenhum banco de histórico encontrado" in explore_module.console.export_text()


def test_db_sem_tabelas_mostra_msgs_dim(monkeypatch, tmp_path):
    monkeypatch.setattr(explore_module, "console", Console(record=True))
    db_file = tmp_path / "empty.sqlite"
    sqlite3.connect(db_file).close()
    _run_explore(str(db_file))
    text = explore_module.console.export_text()
    assert "Tabela 'pipeline_runs' vazia ou não criada" in text
    assert "Histórico de decisões humanas não disponível" in text


def test_db_com_dados_nas_duas_tabelas(monkeypatch, tmp_path):
    monkeypatch.setattr(explore_module, "console", Console(record=True))
    db_file = tmp_path / "data.sqlite"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE pipeline_runs(id TEXT, idea TEXT, status TEXT, stack TEXT, duration_seconds REAL, created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE human_decisions(id TEXT, run_id TEXT, gate_node TEXT, action TEXT, feedback_category TEXT, feedback_message TEXT, timestamp TEXT)"
    )
    cur.executemany(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("id-1", "Ideia done", "done", "python", 12.3, "2026-01-01 00:00:00"),
            ("id-2", "Ideia failed", "failed", "go", 2.7, "2026-01-02 00:00:00"),
            ("id-3", "Ideia running", "running", "rust", 1.0, "2026-01-03 00:00:00"),
        ],
    )
    cur.executemany(
        "INSERT INTO human_decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("d-1", "id-1", "qa", "approve", "ok", "segue", "2026-01-03 10:00:00"),
            ("d-2", "id-2", "dev", "abort", "bug", "parar", "2026-01-03 11:00:00"),
            ("d-3", "id-3", "audit", "retry", "seg", "tentar", "2026-01-03 12:00:00"),
        ],
    )
    conn.commit()
    conn.close()

    _run_explore(str(db_file))
    text = explore_module.console.export_text()
    assert "Execuções Recentes de Pipeline (runs)" in text
    assert "Histórico de Decisões Humana (HITL)" in text
    assert "done" in text and "failed" in text and "running" in text
    assert "approve" in text and "abort" in text and "retry" in text


def test_db_com_tabelas_vazias(monkeypatch, tmp_path):
    monkeypatch.setattr(explore_module, "console", Console(record=True))
    db_file = tmp_path / "empty_tables.sqlite"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE pipeline_runs(id TEXT, idea TEXT, status TEXT, stack TEXT, duration_seconds REAL, created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE human_decisions(id TEXT, run_id TEXT, gate_node TEXT, action TEXT, feedback_category TEXT, feedback_message TEXT, timestamp TEXT)"
    )
    conn.commit()
    conn.close()

    _run_explore(str(db_file))
    text = explore_module.console.export_text()
    assert "Execuções Recentes de Pipeline (runs)" not in text
    assert "Histórico de Decisões Humana (HITL)" not in text
    assert "Nenhuma decisão humana (HITL) gravada ainda." in text
