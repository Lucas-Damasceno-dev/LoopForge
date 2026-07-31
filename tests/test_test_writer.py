from __future__ import annotations

from lf.pipeline.nodes.test_writer import test_writer


def test_test_writer_sem_user_stories_nao_chama_llm_e_retorna_contract_tests_vazio(monkeypatch):
    called = {"value": False}

    def _fake_call_llm_via_opencode(**kwargs):
        called["value"] = True
        return ""

    monkeypatch.setattr("lf.pipeline.nodes.test_writer.call_llm_via_opencode", _fake_call_llm_via_opencode)

    state = {
        "user_stories": [],
        "stack": "python",
        "tech_spec": "spec",
        "output_dir": ".",
        "mock_llm": False,
    }

    result = test_writer(state)

    assert called["value"] is False
    assert result["contract_tests"] == ""


def test_test_writer_com_criterios_gera_contract_tests_e_grava_arquivos(tmp_path, monkeypatch):
    llm_response = """### FILE: tests/test_auth_contract.py
```python
def test_login_valido():
    assert True
```
"""
    state = {
        "user_stories": [
            {
                "id": "US-1",
                "title": "Login com credenciais",
                "acceptance_criteria": ["Deve autenticar usuário válido", "Deve rejeitar senha inválida"],
            }
        ],
        "stack": "python",
        "tech_spec": "Tech spec de exemplo",
        "output_dir": str(tmp_path),
        "mock_llm": True,
    }
    monkeypatch.setattr(
        "lf.pipeline.nodes.test_writer.call_llm_via_opencode",
        lambda **kwargs: llm_response,
    )

    result = test_writer(state)

    assert result["contract_tests"] != ""
    assert (tmp_path / "tests").exists()
    test_files = list((tmp_path / "tests").rglob("*"))
    assert any(p.is_file() for p in test_files)


def test_test_writer_com_parse_falhando_nao_quebra(monkeypatch, tmp_path):
    def _fake_parse(*args, **kwargs):
        raise ValueError("parse falhou")

    monkeypatch.setattr("lf.pipeline.nodes.test_writer._parse_multi_file_response", _fake_parse)

    state = {
        "user_stories": [
            {
                "id": "US-2",
                "title": "Cadastro de usuário",
                "acceptance_criteria": ["Deve cadastrar com e-mail válido"],
            }
        ],
        "stack": "python",
        "tech_spec": "Tech spec",
        "output_dir": str(tmp_path),
        "mock_llm": True,
    }

    result = test_writer(state)

    assert result["contract_tests"] == ""
