"""LoopForge v6 - Autonomous Agent Governance and Pipeline Orchestrator."""

from lf.pipeline.plugins import clear_registered_nodes, get_registered_nodes, register_node, unregister_node

__version__ = "6.0.0"

__all__ = [
    "__version__",
    "register_node",
    "unregister_node",
    "get_registered_nodes",
    "clear_registered_nodes",
]
