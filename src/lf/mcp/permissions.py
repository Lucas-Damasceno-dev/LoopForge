class MCPPermissionError(Exception):
    """Tool não permitida pela allowlist do ade.yaml."""


class MCPUnavailableError(Exception):
    """Servidor MCP não respondeu."""
