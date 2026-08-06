class MCPPermissionDenied(Exception):
    """Tool não permitida pela allowlist do ade.yaml."""


class MCPUnavailable(Exception):
    """Servidor MCP não respondeu."""
