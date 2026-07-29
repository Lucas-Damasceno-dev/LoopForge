"""Testes para elevar a cobertura de código nos módulos críticos (OpenCode, API, Tech Lead, QA)."""

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from lf.api.app import create_app
from lf.api.auth import verify_authentication
from lf.api.config import get_api_settings
from lf.api.database import close_db, init_db
from lf.pipeline.nodes.qa import qa
from lf.pipeline.nodes.tech_lead import tech_lead
from lf.runner.opencode.llm import (
    _extract_json_from_text,
    call_llm_via_opencode,
)
from lf.runner.opencode.models import OpenCodeResult, strip_ansi
from lf.runner.opencode.runner import OpenCodeRunner, detect_changed_files


class DummySchema(BaseModel):
    title: str = Field(...)
    count: int = Field(0)


@pytest.fixture(autouse=True)
async def setup_test_env():
    os.environ["LF_API_TEST"] = "1"
    await init_db()
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)


# ─── 1. Testes de OpenCode Runner & LLM (runner.py & llm.py) ────────
def test_opencode_runner_error_cases(tmp_path):
    with patch.dict("os.environ", {"OPENCODE_MOCK": "1"}):
        runner = OpenCodeRunner(timeout_seconds=5)
        res = runner.run("prompt", project_root=tmp_path)
        assert res.success is True
        assert res.exit_code == 0


def test_detect_changed_files_empty(tmp_path):
    files = detect_changed_files(tmp_path, 0)
    assert isinstance(files, list)


def test_extract_json_edge_cases():
    assert _extract_json_from_text("") is None
    assert _extract_json_from_text("Invalid text without json") is None
    assert _extract_json_from_text("```json\n{\"title\": \"ABC\", \"count\": 5}\n```") == {"title": "ABC", "count": 5}
    assert _extract_json_from_text("Result: {\"title\": \"XYZ\", \"count\": 2} done") == {"title": "XYZ", "count": 2}


def test_opencode_result_and_strip_ansi():
    res = OpenCodeResult(exit_code=0, stdout="\x1b[32mhello\x1b[0m", stderr="")
    assert res.success is True
    assert res.clean_stdout == "hello"
    assert strip_ansi("\x1b[31mtest\x1b[0m") == "test"



def test_call_llm_via_opencode_with_schema_mock():
    res = call_llm_via_opencode(
        system_prompt="sys",
        user_prompt="usr",
        schema_model=DummySchema,
        mock=True,
    )
    assert isinstance(res, dict)
    assert "title" in res


# ─── 2. Testes de API Auth & WebSockets (api/app.py & auth.py) ───────
@pytest.mark.asyncio
async def test_api_auth_enabled():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Patch config to require auth
        with patch("lf.api.auth.APISettings") as mock_settings:
            mock_inst = MagicMock()
            mock_inst.require_auth = True
            mock_inst.api_key = "secret123"
            mock_settings.return_value = mock_inst

            # Without header -> 401
            unauth_resp = await ac.get("/api/runs")
            assert unauth_resp.status_code == 401

            # With correct header -> 200
            auth_resp = await ac.get("/api/runs", headers={"X-API-Key": "secret123"})
            assert auth_resp.status_code == 200


@pytest.mark.asyncio
async def test_api_process_time_header():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert "X-Process-Time" in resp.headers


# ─── 3. Testes do Nó Tech Lead (tech_lead.py) ────────────────────────
def test_tech_lead_node_execution(tmp_path):
    state = {
        "user_stories": [{"id": "US001", "title": "Setup DB"}],
        "output_dir": str(tmp_path),
        "mock_llm": True,
    }
    res = tech_lead(state)
    assert res["next_agent"] == "developer"
    assert "tech_spec" in res
    assert len(res["tech_spec"]) > 0


# ─── 4. Testes do Nó QA (qa.py) ──────────────────────────────────────
def test_qa_node_mock_execution(tmp_path):
    state = {
        "code": "def hello(): pass",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": True,
    }
    res = qa(state)
    assert res["next_agent"] == "appsec"
    assert "test_report" in res
