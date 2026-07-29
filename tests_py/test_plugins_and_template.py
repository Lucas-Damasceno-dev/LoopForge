"""Testes do sistema de plugins e do carregador de templates HTML."""

import os
from pathlib import Path

import lf
from lf.api.dashboard_html import get_dashboard_html
from lf.pipeline.graph import build_graph
from lf.pipeline.plugins import clear_registered_nodes, get_registered_nodes, register_node, unregister_node


def test_contrib_directory_removed():
    contrib_path = Path("src/lf/contrib")
    assert not contrib_path.exists() or not (contrib_path / "api").exists()


def test_dashboard_template_loading():
    html = get_dashboard_html()
    assert "LoopForge v6" in html
    assert "<!DOCTYPE html>" in html


def test_plugin_system_registration():
    clear_registered_nodes()

    def my_custom_node(state):
        return {**state, "next_agent": "FINISH"}

    lf.register_node("my_custom_node", my_custom_node)
    nodes = get_registered_nodes()
    assert "my_custom_node" in nodes

    graph = build_graph()
    assert graph is not None

    unregister_node("my_custom_node")
    assert "my_custom_node" not in get_registered_nodes()
