"""Testes dos endpoints MCP da ADE (GET /api/v1/mcp/servers, /tools e POST tool).

O teste de GET usa um servidor MCP FAKE real (subprocesso stdio, mesmo padrão
original); os testes de POST tool mockam ``lf.api.mcp._registry`` para isolar
os mapeamentos de erro (403/503/404) sem subprocesso.
"""

import sys

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.config.loader import load_ade_config, save_ade_config
from lf.config.schema import AdeConfig, AdeMcpServer
from lf.mcp.permissions import MCPPermissionError, MCPUnavailableError

FAKE = r"""
import asyncio

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server


async def handle_list_tools(ctx, params):
    return types.ListToolsResult(
        tools=[types.Tool(name="ping", description="p", input_schema={"type": "object"})]
    )


async def handle_call_tool(ctx, params):
    return types.CallToolResult(content=[types.TextContent(type="text", text="pong")])


server = Server(
    "t",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


asyncio.run(main())
"""


@pytest.mark.asyncio
async def test_mcp_api_lists_servers_and_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "fake.py"
    fake.write_text(FAKE)
    save_ade_config(
        AdeConfig(
            mcp_servers=[AdeMcpServer(name="t", command=sys.executable, args=[str(fake)], tools_allowlist=["ping"])]
        ),
        tmp_path / ".loopforge" / "ade.yaml",
    )
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/mcp/servers")
        assert r.status_code == 200
        assert any(s["name"] == "t" for s in r.json())
        r2 = await ac.get("/api/v1/mcp/servers/t/tools")
        assert r2.status_code == 200
        assert [t["name"] for t in r2.json()] == ["ping"]


# ─── POST /api/v1/mcp/servers/{name}/tools/{tool} (D2) ─────────────────────


class _FakeRegistry:
    """Registry stub para os testes de POST tool (start/stop no try/finally)."""

    def __init__(self, config, call_result=None, errors=None):
        self.config = config
        self.call_result = call_result
        self.errors = errors or {}  # {(server, tool): exception}
        self.started = False
        self.stopped = False

    async def start_all(self):
        self.started = True

    async def stop_all(self):
        self.stopped = True

    async def call_tool(self, server, name, args):
        exc = self.errors.get((server, name))
        if exc is not None:
            raise exc
        return self.call_result


def _write_ade(tmp_path, servers):
    save_ade_config(AdeConfig(mcp_servers=servers), tmp_path / ".loopforge" / "ade.yaml")
    return load_ade_config()


@pytest.mark.asyncio
async def test_mcp_call_tool_success_with_allowlist(tmp_path, monkeypatch):
    """POST tool retorna 200 com o dict do call_tool (allowlist ok)."""
    monkeypatch.chdir(tmp_path)
    cfg = _write_ade(
        tmp_path,
        [AdeMcpServer(name="t", command="python", args=[], tools_allowlist=["ping"])],
    )
    fake = _FakeRegistry(config=cfg, call_result={"content": [{"type": "text", "text": "pong"}]})
    monkeypatch.setattr("lf.api.mcp._registry", lambda: fake)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/mcp/servers/t/tools/ping", json={"arguments": {"x": 1}})
        assert r.status_code == 200
        assert r.json() == {"content": [{"type": "text", "text": "pong"}]}
        # arguments é opcional (default {}) — POST sem body também funciona
        r2 = await ac.post("/api/v1/mcp/servers/t/tools/ping")
        assert r2.status_code == 200
    assert fake.started and fake.stopped, "start_all/stop_all devem rodar no try/finally"


@pytest.mark.asyncio
async def test_mcp_call_tool_403_fora_da_allowlist(tmp_path, monkeypatch):
    """Tool fora da allowlist → 403 com detail PT (MCPPermissionError)."""
    monkeypatch.chdir(tmp_path)
    cfg = _write_ade(
        tmp_path,
        [AdeMcpServer(name="t", command="python", args=[], tools_allowlist=["ping"])],
    )
    fake = _FakeRegistry(
        config=cfg,
        errors={("t", "hack"): MCPPermissionError("Tool t:hack não permitida (allowlist do ade.yaml)")},
    )
    monkeypatch.setattr("lf.api.mcp._registry", lambda: fake)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/mcp/servers/t/tools/hack", json={"arguments": {}})
        assert r.status_code == 403
        assert "não permitida" in r.json()["detail"]


@pytest.mark.asyncio
async def test_mcp_call_tool_503_server_nao_conectado(tmp_path, monkeypatch):
    """Servidor não conectado → 503 com detail PT (MCPUnavailableError)."""
    monkeypatch.chdir(tmp_path)
    cfg = _write_ade(
        tmp_path,
        [AdeMcpServer(name="t", command="python", args=[], tools_allowlist=["ping"])],
    )
    fake = _FakeRegistry(
        config=cfg,
        errors={("t", "ping"): MCPUnavailableError("Servidor MCP t não conectado")},
    )
    monkeypatch.setattr("lf.api.mcp._registry", lambda: fake)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/mcp/servers/t/tools/ping", json={"arguments": {}})
        assert r.status_code == 503
        assert "não conectado" in r.json()["detail"]


@pytest.mark.asyncio
async def test_mcp_call_tool_404_server_inexistente(tmp_path, monkeypatch):
    """Server ausente do ade.yaml → 404 (não vira 503/403)."""
    monkeypatch.chdir(tmp_path)
    cfg = _write_ade(tmp_path, [])  # nenhum servidor declarado
    fake = _FakeRegistry(config=cfg, call_result={})
    monkeypatch.setattr("lf.api.mcp._registry", lambda: fake)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/mcp/servers/nao-existe/tools/foo", json={"arguments": {}})
        assert r.status_code == 404
        assert "não existe no ade.yaml" in r.json()["detail"]
