"""Testes dos endpoints MCP da ADE (GET /api/v1/mcp/servers e /tools)."""

import sys

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.config.loader import save_ade_config
from lf.config.schema import AdeConfig, AdeMcpServer

FAKE = r'''
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
'''


@pytest.mark.asyncio
async def test_mcp_api_lists_servers_and_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake = tmp_path / "fake.py"
    fake.write_text(FAKE)
    save_ade_config(AdeConfig(mcp_servers=[AdeMcpServer(name="t", command=sys.executable,
                                                        args=[str(fake)], tools_allowlist=["ping"])]),
                    tmp_path / ".loopforge" / "ade.yaml")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/mcp/servers")
        assert r.status_code == 200
        assert any(s["name"] == "t" for s in r.json())
        r2 = await ac.get("/api/v1/mcp/servers/t/tools")
        assert r2.status_code == 200
        assert [t["name"] for t in r2.json()] == ["ping"]
