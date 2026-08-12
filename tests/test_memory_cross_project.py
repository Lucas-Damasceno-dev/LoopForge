"""Testes da memória cross-project (ROADMAP 3.1).

``MemoryManager.list_lessons/search_relevant_lessons`` ganham ``cross_project``:
True → o filtro de stack é ignorado (todas as stacks entram no contexto);
False (default) → comportamento atual preservado.
"""

from lf.config.schema import AdeConfig, AdeMemory
from lf.memory.manager import MemoryManager, cross_project_enabled


def _seed(manager: MemoryManager) -> None:
    manager.save_lesson("run-1", "python", "API REST", "Use pydantic-settings para config.")
    manager.save_lesson("run-2", "java", "Padrões GoF", "Prefira interfaces a herança.")


def test_list_lessons_default_filters_by_stack(tmp_path):
    """Default (cross_project=False) mantém o filtro de stack atual."""
    manager = MemoryManager(tmp_path / "memory.sqlite")
    _seed(manager)

    assert {x["stack"] for x in manager.list_lessons(stack="python")} == {"python"}
    assert {x["stack"] for x in manager.list_lessons(stack="java")} == {"java"}
    assert {x["stack"] for x in manager.list_lessons()} == {"python", "java"}


def test_list_lessons_cross_project_ignores_stack(tmp_path):
    """cross_project=True ignora o filtro de stack (todas as stacks)."""
    manager = MemoryManager(tmp_path / "memory.sqlite")
    _seed(manager)

    lessons = manager.list_lessons(stack="python", cross_project=True)
    assert {x["stack"] for x in lessons} == {"python", "java"}


def test_search_relevant_default_filters_by_stack(tmp_path):
    """Default: busca por relevância respeita a stack (BC)."""
    manager = MemoryManager(tmp_path / "memory.sqlite")
    _seed(manager)

    hits = manager.search_relevant_lessons("pydantic settings", stack="java", only_relevant=True)
    assert hits == []

    hits = manager.search_relevant_lessons("pydantic settings", stack="python", only_relevant=True)
    assert {x["stack"] for x in hits} == {"python"}


def test_search_relevant_cross_project_ignores_stack(tmp_path):
    """cross_project=True encontra lições de outras stacks na busca."""
    manager = MemoryManager(tmp_path / "memory.sqlite")
    _seed(manager)

    hits = manager.search_relevant_lessons("pydantic settings", stack="java", cross_project=True, only_relevant=True)
    assert {x["stack"] for x in hits} == {"python"}
    assert len(hits) == 1


def test_cross_project_enabled_config():
    """cross_project_enabled lê AdeConfig.memory.cross_project (default False)."""
    assert cross_project_enabled(AdeConfig()) is False
    assert cross_project_enabled(AdeConfig(memory=AdeMemory(cross_project=True))) is True
