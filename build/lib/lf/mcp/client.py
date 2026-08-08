from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from lf.config.schema import AdeMcpServer


class MCPClient:
    """Cliente stdio por servidor MCP (SDK oficial)."""

    def __init__(self, spec: AdeMcpServer):
        self.spec = spec
        self._session: ClientSession | None = None
        self._ctx = None

    async def connect(self) -> None:
        params = StdioServerParameters(command=self.spec.command, args=self.spec.args)
        self._ctx = stdio_client(params)
        read, write = await self._ctx.__aenter__()
        self._session = await ClientSession(read, write).__aenter__()
        await self._session.initialize()

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._ctx is not None:
            await self._ctx.__aexit__(None, None, None)
            self._ctx = None

    async def list_tools(self) -> list[dict]:
        if self._session is None:
            raise RuntimeError("MCPClient não conectado")
        resp = await self._session.list_tools()
        # mcp 2.x expõe input_schema (SDK); o contrato ADE usa a chave inputSchema.
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in resp.tools
        ]

    async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("MCPClient não conectado")
        result = await self._session.call_tool(name, arguments=args)
        return result.model_dump()
