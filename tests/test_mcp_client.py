import asyncio
import json
import sys
from pathlib import Path
import pytest
from lf.config.schema import AdeConfig, AdeMcpServer
from lf.mcp.permissions import MCPPermissionDenied
from lf.mcp.registry import MCPRegistry

FAKE_SERVER_SRC = r'''
import asyncio
import json

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server


async def handle_list_tools(ctx, params):
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="echo",
                description="echo input",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
            )
        ]
    )


async def handle_call_tool(ctx, params):
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(params.arguments or {}))]
    )


server = Server(
    "fake-tools",
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


asyncio.run(main())
'''


@pytest.fixture
def fake_server_script(tmp_path) -> Path:
    p = tmp_path / "fake_server.py"
    p.write_text(FAKE_SERVER_SRC)
    return p


@pytest.mark.asyncio
async def test_registry_lists_and_calls_tool(fake_server_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = AdeConfig(mcp_servers=[AdeMcpServer(name="fake", command=sys.executable,
                                              args=[str(fake_server_script)], tools_allowlist=["echo"])])
    registry = MCPRegistry(cfg)
    await registry.start_all()
    try:
        servers = await registry.list_servers()
        assert servers[0]["name"] == "fake"
        tools = await registry.list_tools("fake")
        assert [t["name"] for t in tools] == ["echo"]
        result = await registry.call_tool("fake", "echo", {"text": "oi"})
        assert "oi" in json.dumps(result)
    finally:
        await registry.stop_all()


@pytest.mark.asyncio
async def test_permission_denied_raises(fake_server_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = AdeConfig(mcp_servers=[AdeMcpServer(name="fake", command=sys.executable,
                                              args=[str(fake_server_script)], tools_allowlist=["other"])])
    registry = MCPRegistry(cfg)
    await registry.start_all()
    try:
        with pytest.raises(MCPPermissionDenied):
            await registry.call_tool("fake", "echo", {"text": "x"})
    finally:
        await registry.stop_all()
