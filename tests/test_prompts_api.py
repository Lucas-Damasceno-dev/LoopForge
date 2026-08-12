"""Testes da Prompt Central: API CRUD de overrides + injeção nos nós.

Cobre:
  - GET /api/v1/prompts lista defaults e reflete overrides persistidos;
  - PATCH salva override (e valida node desconhecido/prompt vazio);
  - DELETE remove override (404 quando não existe);
  - get_effective_prompt aplica override via path injetado;
  - o nó developer usa o override persistido como system_prompt.
"""

import contextlib
import json
import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.pipeline.prompt_overrides import (
    delete_prompt_override,
    get_effective_prompt,
    set_prompt_override,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco SQLite de teste limpo (padrão test_api.py)."""
    from lf.api.database import Base, close_db, engine, init_db

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in (
        ".loopforge/test_api.sqlite",
        ".loopforge/test_api.sqlite-wal",
        ".loopforge/test_api.sqlite-shm",
    ):
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """Client ASGI isolado: CWD no tmp_path (overrides ficam em .loopforge/)."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─── GET ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prompts_list_defaults(client: AsyncClient):
    """GET lista os 6 nós com prompt padrão embutido (sem overrides)."""
    r = await client.get("/api/v1/prompts")
    assert r.status_code == 200
    entries = r.json()
    assert {e["node"] for e in entries} == {
        "cpo",
        "pm",
        "tech_lead",
        "test_writer",
        "developer",
        "appsec",
    }
    by_node = {e["node"]: e["prompt"] for e in entries}
    assert "Você é um CPO" in by_node["cpo"]
    assert "Desenvolvedor Sênior" in by_node["developer"]
    assert "AppSec" in by_node["appsec"]


# ─── PATCH ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prompts_patch_override_visible_on_get(client: AsyncClient):
    """PATCH salva override e GET passa a devolvê-lo."""
    r = await client.patch("/api/v1/prompts/cpo", json={"prompt": "Prompt customizado do CPO."})
    assert r.status_code == 200
    assert r.json() == {"node": "cpo", "prompt": "Prompt customizado do CPO."}

    r = await client.get("/api/v1/prompts")
    entries = {e["node"]: e["prompt"] for e in r.json()}
    assert entries["cpo"] == "Prompt customizado do CPO."
    # Demais nós seguem com defaults intactos.
    assert "Você é um CPO" not in entries["cpo"]
    assert "Desenvolvedor Sênior" in entries["developer"]


@pytest.mark.asyncio
async def test_prompts_patch_unknown_node_404(client: AsyncClient):
    """PATCH em node fora do registry → 404."""
    r = await client.patch("/api/v1/prompts/qa", json={"prompt": "qualquer"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_prompts_patch_empty_prompt_422(client: AsyncClient):
    """PATCH com prompt vazio → 422 (pydantic min_length + validação explícita)."""
    r = await client.patch("/api/v1/prompts/cpo", json={"prompt": "   "})
    assert r.status_code == 422


# ─── DELETE ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prompts_delete_restores_default(client: AsyncClient):
    """DELETE remove override e GET volta ao default embutido."""
    await client.patch("/api/v1/prompts/cpo", json={"prompt": "Override temporário."})
    r = await client.delete("/api/v1/prompts/cpo")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}

    entries = {e["node"]: e["prompt"] for e in (await client.get("/api/v1/prompts")).json()}
    assert "Você é um CPO" in entries["cpo"]


@pytest.mark.asyncio
async def test_prompts_delete_without_override_404(client: AsyncClient):
    """DELETE sem override existente → 404."""
    r = await client.delete("/api/v1/prompts/developer")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_prompts_delete_unknown_node_404(client: AsyncClient):
    """DELETE em node fora do registry → 404."""
    r = await client.delete("/api/v1/prompts/devops")
    assert r.status_code == 404


# ─── Unidade: prompt_overrides ────────────────────────────────────────────
def test_get_effective_prompt_override_via_path(tmp_path):
    """Override aplicado via path explícito; sem override → default."""
    overrides_path = tmp_path / "overrides.json"
    set_prompt_override("cpo", "Override CPO.", overrides_path)
    assert get_effective_prompt("cpo", "Default CPO.", overrides_path) == "Override CPO."
    assert get_effective_prompt("pm", "Default PM.", overrides_path) == "Default PM."
    assert delete_prompt_override("cpo", overrides_path) is True
    assert delete_prompt_override("cpo", overrides_path) is False


def test_get_effective_prompt_io_failure_falls_back(tmp_path):
    """Path inexistente/corrompido → default (falha de I/O nunca quebra)."""
    assert get_effective_prompt("cpo", "Default CPO.", tmp_path / "nao-existe.json") == "Default CPO."

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{{{ json inválido", encoding="utf-8")
    assert get_effective_prompt("cpo", "Default CPO.", corrupt) == "Default CPO."


def test_set_prompt_override_persists_atomically(tmp_path):
    """Override persiste em disco e lê de volta."""
    overrides_path = tmp_path / "overrides.json"
    set_prompt_override("developer", "Override Dev.", overrides_path)
    assert json.loads(overrides_path.read_text(encoding="utf-8")) == {"developer": "Override Dev."}
    # Sobrescreve sem duplicar.
    set_prompt_override("developer", "Override Dev v2.", overrides_path)
    assert json.loads(overrides_path.read_text(encoding="utf-8")) == {"developer": "Override Dev v2."}


# ─── Nó usa override ──────────────────────────────────────────────────────
def test_developer_node_uses_override(tmp_path, monkeypatch):
    """Developer envia o override persistido como system_prompt."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".loopforge").mkdir(exist_ok=True)
    (tmp_path / ".loopforge" / "prompts_overrides.json").write_text(
        json.dumps({"developer": "OVERRIDE_DEV_PROMPT"}), encoding="utf-8"
    )

    state = {
        "idea": "Serviço REST em Python",
        "stack": "python",
        "mock_llm": False,
        "output_dir": str(tmp_path),
        "user_stories": [{"id": "US1", "title": "Criar API"}],
        "tech_spec": "Tech Spec de teste",
    }
    captured: list[str] = []

    def mock_call_llm(system_prompt: str, **kwargs):
        captured.append(system_prompt)
        return "### FILE: src/main.py\nprint('ok')"

    from lf.pipeline.nodes.developer import developer

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=mock_call_llm):
        developer(state)

    assert captured, "developer deveria chamar a LLM"
    assert captured[0] == "OVERRIDE_DEV_PROMPT"
