"""Endpoints MCP da ADE (lista de servidores e ferramentas)."""
from fastapi import APIRouter, Depends, HTTPException

from lf.api.auth import verify_authentication
from lf.config.loader import load_ade_config
from lf.mcp.permissions import MCPUnavailable
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
