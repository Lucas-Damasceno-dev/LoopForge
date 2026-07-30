"""Suíte de testes automatizados para o Agentic Retro."""

import json
import os
import tempfile
import pytest

from retro.core.analyzer import SessionAnalyzer
from retro.core.parser import AgDRParser
from retro.core.recommender import Recommender
from retro.report.renderer import RetroRenderer
from retro.store.sqlite import RetroStore


def test_agdr_parser_and_analyzer():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "session.jsonl")
        events_json = [
            {"type": "session_start", "session_id": "lf-run-001", "goal": "API REST em Python com FastAPI"},
            {"type": "node_start", "node": "developer", "attempt": 1},
            {"type": "node_error", "node": "qa", "error": "integration test sem DB mock", "attempt": 1},
            {"type": "node_retry", "node": "developer", "feedback": "Adicionar mock DB", "attempt": 2},
            {"type": "node_success", "node": "qa", "attempt": 2},
            {"type": "session_end", "session_id": "lf-run-001", "status": "PASS", "duration_ms": 12500, "cost": 0.15},
        ]
        with open(log_path, "w", encoding="utf-8") as f:
            for ev in events_json:
                f.write(json.dumps(ev) + "\n")

        parser = AgDRParser()
        session = parser.parse_file(log_path)

        assert session.session_id == "lf-run-001"
        assert session.goal == "API REST em Python com FastAPI"
        assert session.status == "PASS"
        assert session.attempts == 2

        analyzer = SessionAnalyzer()
        patterns = analyzer.analyze(session)
        assert len(patterns) >= 1
        assert any(p.pattern == "qa-db-mock" for p in patterns)

        recommender = Recommender()
        learnings = recommender.recommend(session, patterns)
        assert len(learnings) >= 1
        assert any("Mock DB" in l.recommendation for l in learnings)

        renderer = RetroRenderer()
        report = renderer.render(session, patterns, learnings)
        assert report.session_id == "lf-run-001"
        assert "# 🧠 Agentic Retro" in report.summary_md
        assert "qa-db-mock" in report.summary_md


def test_retro_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = AgDRParser()
        session = parser.parse_events([])
        session.session_id = "test-123"
        session.goal = "CLI Tool"
        session.status = "PASS"

        store = RetroStore(tmpdir)
        store.save_session(session)

        loaded = store.load_session("test-123")
        assert loaded is not None
        assert loaded.session_id == "test-123"

        sessions = store.list_sessions()
        assert len(sessions) == 1
