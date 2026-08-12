from typing import Any

from lf.config.schema import AdeConfig
from lf.mcp.client import MCPClient
from lf.mcp.permissions import MCPPermissionDenied, MCPUnavailable


class MCPRegistry:
    """Dono dos clientes MCP ativos; start/stop por server declarado no ade.yaml."""

    def __init__(self, config: AdeConfig):
        self.config = config
        self._clients: dict[str, MCPClient] = {}
        self._status: dict[str, str] = {}

    async def start_all(self) -> None:
        for spec in self.config.mcp_servers:
            if not spec.enabled:
                continue
            client = MCPClient(spec)
            try:
                await client.connect()
                self._status[spec.name] = "connected"
            except Exception:
                self._status[spec.name] = "unavailable"
            self._clients[spec.name] = client

    async def stop_all(self) -> None:
        for client in self._clients.values():
            try:
                await client.disconnect()
            except Exception:
                pass
        self._clients.clear()

    def _server(self, name: str) -> MCPClient:
        if name not in self._clients:
            raise MCPUnavailable(f"Servidor MCP {name} não disponível")
        return self._clients[name]

    async def list_servers(self) -> list[dict]:
        return [{"name": s.name, "status": self._status.get(s.name, "stopped")} for s in self.config.mcp_servers]

    async def list_tools(self, server: str) -> list[dict]:
        if self._status.get(server) != "connected":
            raise MCPUnavailable(f"Servidor MCP {server} não conectado")
        spec = next((s for s in self.config.mcp_servers if s.name == server), None)
        allowlist = spec.tools_allowlist if spec is not None else []
        tools = await self._server(server).list_tools()
        # Superfície da allowlist deny-by-default: cada tool expõe `allowed`
        # (False quando fora da allowlist — allowlist vazia = tudo negado).
        for t in tools:
            t["allowed"] = t["name"] in allowlist
        return tools

    async def call_tool(self, server: str, name: str, args: dict[str, Any]) -> Any:
        spec = next((s for s in self.config.mcp_servers if s.name == server), None)
        if spec is None or name not in spec.tools_allowlist:
            raise MCPPermissionDenied(f"Tool {server}:{name} não permitida (allowlist do ade.yaml)")
        if self._status.get(server) != "connected":
            raise MCPUnavailable(f"Servidor MCP {server} não conectado")
        try:
            return await self._server(server).call_tool(name, args)
        except MCPPermissionDenied:
            raise
        except Exception as exc:
            self._status[server] = "unavailable"
            raise MCPUnavailable(f"Falha ao chamar {server}:{name}") from exc
