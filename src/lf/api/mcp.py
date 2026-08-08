"""Endpoints MCP da ADE (lista de servidores, ferramentas e chamada de tool)."""

from fastapi import APIRouter, Depends, HTTPException

from lf.api.auth import verify_authentication
from lf.api.schemas import MCPToolCallRequest
from lf.config.loader import load_ade_config
from lf.mcp.permissions import MCPPermissionDenied, MCPUnavailable
from lf.mcp.registry import MCPRegistry

mcp_router = APIRouter(
    prefix="/api/v1/mcp",
    tags=["MCP"],
    dependencies=[Depends(verify_authentication)],  # M-03: auth em todas as rotas
)


def _registry() -> MCPRegistry:
    return MCPRegistry(load_ade_config())


@mcp_router.get("/servers")
async def list_servers():
    reg = _registry()
    try:
        await reg.start_all()
        return await reg.list_servers()
    finally:
        await reg.stop_all()


@mcp_router.get("/servers/{name}/tools")
async def list_server_tools(name: str):
    reg = _registry()
    try:
        await reg.start_all()
        try:
            return await reg.list_tools(name)
        except MCPUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await reg.stop_all()


@mcp_router.post("/servers/{name}/tools/{tool}")
async def call_server_tool(
    name: str,
    tool: str,
    payload: MCPToolCallRequest | None = None,
):
    """Chama uma tool MCP do servidor (D2): 200 dict, 403 fora da allowlist,
    404 servidor inexistente no ade.yaml, 503 servidor não conectado."""
    reg = _registry()
    try:
        await reg.start_all()
        try:
            # 404: server inexistente no ade.yaml (o registry mapearia isso
            # para MCPPermissionDenied/MCPUnavailable — o 404 é mais preciso).
            if not any(s.name == name for s in reg.config.mcp_servers):
                raise HTTPException(
                    status_code=404,
                    detail=f"Servidor MCP {name} não existe no ade.yaml",
                )
            args = payload.arguments if payload is not None else {}
            return await reg.call_tool(name, tool, args)
        except MCPPermissionDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except MCPUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await reg.stop_all()
