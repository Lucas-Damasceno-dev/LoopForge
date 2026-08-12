"""Suíte de testes para os padrões Registry de desacoplamento do LoopForge."""

import os

from genome import BaseLanguageScanner, GenomeScanner, ModuleInfo

from lf.config.registry import BaseStackHandler, TechStackRegistry
from lf.config.schema import resolve_tech_stack
from lf.pipeline.graph import EdgeRegistry, NodeRegistry, build_graph


class ElixirStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "elixir"

    @property
    def default_framework(self) -> str:
        return "phoenix"

    @property
    def default_test_harness(self) -> str:
        return "mix test"

    @property
    def default_package_manager(self) -> str:
        return "mix"

    def detect_test_command(self, project_dir: str) -> str | None:
        if os.path.exists(os.path.join(project_dir, "mix.exs")):
            return "mix test"
        return None


class DummyScanner(BaseLanguageScanner):
    @property
    def language_name(self) -> str:
        return "dummy"

    @property
    def extensions(self) -> list[str]:
        return [".dummy"]

    def scan_file(self, file_path: str, code: str) -> ModuleInfo:
        return ModuleInfo(path=file_path, language="dummy")


def test_tech_stack_registry_extensibility():
    TechStackRegistry.register(ElixirStackHandler())
    resolved = resolve_tech_stack("elixir")
    assert resolved.language == "elixir"
    assert resolved.framework == "phoenix"
    assert resolved.testing_harness == "mix test"
    assert resolved.package_manager == "mix"


def test_genome_scanner_registry():
    GenomeScanner.register_scanner(DummyScanner())
    scanner = GenomeScanner(".")
    assert any(s.language_name == "dummy" for s in scanner.scanners)


def test_node_and_edge_registry():
    def custom_node(state):
        return state

    NodeRegistry.register("custom_node", custom_node)
    EdgeRegistry.register("cpo", {"custom_node": "custom_node"})

    graph = build_graph()
    assert "custom_node" in graph.nodes


def test_aliases_strict_matching():
    js_handler = TechStackRegistry.get("js")
    assert js_handler is not None
    assert js_handler.language == "javascript"

    json_handler = TechStackRegistry.get("json")
    assert json_handler is None
