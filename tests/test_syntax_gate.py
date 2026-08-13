"""Testes do gate sintático (Onda 2, 2.3): validação AST/javac + retry hard no Developer."""

import shutil
from unittest.mock import patch

import pytest

from lf.pipeline.nodes.developer import _check_syntax_and_types, developer


def test_check_syntax_python_valido_retorna_vazio():
    errors = _check_syntax_and_types({"app.py": "def f():\n    return 1\n"}, "python")
    assert errors == []


def test_check_syntax_python_invalido_retorna_erros():
    errors = _check_syntax_and_types({"app.py": "def f(:\n    pass\n"}, "python")
    assert errors
    assert any("SyntaxError" in e for e in errors)


def _developer_state(tmp_path, attempt_count=0, max_retries=3):
    return {
        "idea": "app sintaxe",
        "tech_spec": "# Spec\nImplemente o código",
        "user_stories": [{"id": "US-001", "title": "Feature", "acceptance_criteria": ["c1"]}],
        "stack": "python",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": False,
        "feedback_history": [],
        "attempt_count": attempt_count,
        "max_retries": max_retries,
    }


def test_developer_gate_retorna_para_si_mesmo_quando_sintaxe_invalida(tmp_path):
    """Com retries restantes, o nó retorna next_agent=developer e registra o feedback."""
    state = _developer_state(tmp_path, attempt_count=0)
    with (
        patch(
            "lf.pipeline.nodes.developer.call_llm_via_opencode", return_value="```python\ndef main():\n    pass\n```"
        ),
        patch("lf.pipeline.nodes.developer._check_syntax_and_types", return_value=["err1", "err2"]),
    ):
        res = developer(state)

    assert res["next_agent"] == "developer"
    assert res["attempt_count"] == 1
    last_fb = res["feedback_history"][-1]
    assert last_fb["from"] == "developer"
    assert "Falha no gate sintático" in last_fb["message"]
    assert "err1; err2" in last_fb["message"]


def test_developer_gate_esgotado_segue_para_qa(tmp_path):
    """Com max_retries atingido, o gate não cria loop: segue para o QA com o erro registrado."""
    state = _developer_state(tmp_path, attempt_count=3, max_retries=3)
    with (
        patch(
            "lf.pipeline.nodes.developer.call_llm_via_opencode", return_value="```python\ndef main():\n    pass\n```"
        ),
        patch("lf.pipeline.nodes.developer._check_syntax_and_types", return_value=["err1"]),
    ):
        res = developer(state)

    assert res["next_agent"] == "qa"
    assert res["attempt_count"] == 4
    assert any("Falha no gate sintático" in fb.get("message", "") for fb in res["feedback_history"])


def test_check_syntax_java_erro_de_sintaxe(tmp_path):
    """Cobertura Java: javac com erro de sintaxe gera erro de gate (ignora dependências)."""
    if shutil.which("javac") is None:
        pytest.skip("javac não disponível no ambiente")

    java_dir = tmp_path / "src" / "main" / "java"
    java_dir.mkdir(parents=True)
    main_java = java_dir / "Main.java"
    # Erro de sintaxe: falta ';' após o System.out.println
    main_java.write_text(
        'public class Main {\n    public static void main(String[] args) {\n        System.out.println("oi")\n    }\n}\n',
        encoding="utf-8",
    )
    files_map = {"src/main/java/Main.java": main_java.read_text(encoding="utf-8")}

    errors = _check_syntax_and_types(files_map, "java", str(tmp_path))
    assert errors
    assert any("Java syntax check error" in e for e in errors)


def test_check_syntax_java_valido_ignora_erro_de_dependencia(tmp_path):
    """Java válido mas com dependência externa (cannot find symbol) NÃO deve falhar o gate."""
    if shutil.which("javac") is None:
        pytest.skip("javac não disponível no ambiente")

    java_dir = tmp_path / "src" / "main" / "java"
    java_dir.mkdir(parents=True)
    main_java = java_dir / "Main.java"
    # Sintaxe válida; a chamada a ExternalService geraria 'cannot find symbol'
    # (erro de dependência) — deve ser IGNORADO pelo filtro do gate.
    main_java.write_text(
        "public class Main {\n    public static void main(String[] args) {\n        ExternalService s = new ExternalService();\n        System.out.println(s);\n    }\n}\n",
        encoding="utf-8",
    )
    files_map = {"src/main/java/Main.java": main_java.read_text(encoding="utf-8")}

    errors = _check_syntax_and_types(files_map, "java", str(tmp_path))
    assert errors == []
