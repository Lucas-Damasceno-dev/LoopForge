"""Suíte de testes para a lógica desacoplada do Wizard interativo da CLI."""
from lf.cli.commands.run import _build_wizard_task_schema


def test_build_wizard_task_schema():
    task = _build_wizard_task_schema(
        idea="API de Finanças",
        stack="python",
        complexity="advanced",
        interactive=False,
    )
    assert task.title == "API de Finanças"
    assert task.stack == "python"
    assert task.complexity_level == "advanced"
