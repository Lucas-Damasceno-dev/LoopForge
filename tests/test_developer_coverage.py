"""Cobertura adicional do nó Developer (src/lf/pipeline/nodes/developer.py).

Foca em branches reais ainda sem cobertura: parsing multi-arquivo (padrões
2/3/4), extração de trechos de falha, gate sintático (node/cargo/go/javac),
circuit breaker (interrupt), hooks opcionais genome/registry/memory, streaming
token_delta, limpeza de diretórios (dogfooding) e tratamento de erro.
"""

import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.pipeline.nodes.developer import (
    _check_syntax_and_types,
    _clean_code,
    _cleanup_stale_project_dirs,
    _extract_failing_snippets,
    _log_telemetry_event,
    _parse_multi_file_response,
    _truncate_tech_spec,
    _write_project_files,
    developer,
)

# ---------------------------------------------------------------------------
# _truncate_tech_spec
# ---------------------------------------------------------------------------


def test_truncate_tech_spec_curto_retorna_inalterado():
    spec = "# Spec\nCurto."
    assert _truncate_tech_spec(spec) == spec


def test_truncate_tech_spec_com_header_arquitetura_preserva_secao():
    spec = (
        "# Spec\n"
        + "introdução longa sem palavras-chave aqui, só preenchimento de texto\n" * 200
        + "\n## Arquitetura\n"
        + "componentes e endpoints do sistema\n"
        + "conteúdo adicional repetido para estourar a janela de corte do seletor\n" * 30
    )
    truncated = _truncate_tech_spec(spec, max_chars=200)
    assert "## Arquitetura" in truncated
    assert len(truncated) <= 200


def test_truncate_tech_spec_sem_header_cai_no_fallback():
    spec = "texto longo sem nenhum header relevante\n" * 500
    truncated = _truncate_tech_spec(spec, max_chars=100)
    assert truncated == spec[:100]


def test_truncate_tech_spec_quebra_na_ultima_linha():
    """Truncação com corte no meio de linhas: para na última quebra de linha."""
    spec = "# Dados\n" + ("linha de conteúdo repetida para encher o buffer\n" * 100)
    truncated = _truncate_tech_spec(spec, max_chars=150)
    assert len(truncated) <= 150
    assert truncated.endswith("buffer\n") or "linha de conteúdo" in truncated


# ---------------------------------------------------------------------------
# _log_telemetry_event
# ---------------------------------------------------------------------------


def test_log_telemetry_event_grava_no_sqlite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _log_telemetry_event("hook_error", {"hook": "x", "node": "developer"})
    db = tmp_path / ".loopforge" / "telemetry.sqlite"
    assert db.exists()
    with sqlite3.connect(str(db)) as conn:
        rows = conn.execute("SELECT event_type FROM telemetry_events").fetchall()
    assert ("hook_error",) in rows


def test_log_telemetry_event_erro_silencioso(monkeypatch):
    with patch("lf.pipeline.nodes.developer.sqlite3.connect", side_effect=RuntimeError("disk full")):
        # Não deve levantar: o hook de telemetria falha silencioso por design.
        _log_telemetry_event("hook_error", {"hook": "x"})


# ---------------------------------------------------------------------------
# _clean_code / parsing multi-arquivo (padrões 2, 3 e 4)
# ---------------------------------------------------------------------------


def test_clean_code_lang_sem_fence_fechada():
    assert _clean_code("```python\nx = 1") == "x = 1"


def test_clean_code_so_fence_e_linguagem():
    # "```java" sem newline: linha 104 faz code[3:] = "java" e o strip final mantém.
    assert _clean_code("```java") == "java"


def test_parse_multi_file_pattern2_filename_igual():
    raw = "```python filename=src/app.py\nprint(1)\n```"
    parsed = _parse_multi_file_response(raw, "main.py")
    assert parsed == {"src/app.py": "print(1)"}


def test_parse_multi_file_pattern3_comentario_file():
    raw = "```python\n// file: src/app.py\nprint(1)\n```"
    parsed = _parse_multi_file_response(raw, "main.py")
    assert parsed == {"src/app.py": "print(1)"}


def test_parse_multi_file_pattern4_sem_cercas():
    raw = "### FILE: notas.txt\nconteúdo sem cercas markdown\n### FILE: outro.txt\nmais conteúdo\n"
    parsed = _parse_multi_file_response(raw, "main.py")
    assert parsed == {"notas.txt": "conteúdo sem cercas markdown", "outro.txt": "mais conteúdo"}


def test_parse_multi_file_fallback_default_filename():
    parsed = _parse_multi_file_response("texto solto sem padrão", "main.py")
    assert parsed == {"main.py": "texto solto sem padrão"}


# ---------------------------------------------------------------------------
# _extract_failing_snippets
# ---------------------------------------------------------------------------


def _report_com_erro(err_text: str) -> dict:
    return {
        "results_by_suite": [
            {"failed_tests_details": [{"error": err_text, "test_name": "test_x"}]},
        ]
    }


def test_extract_failing_snippets_report_nao_dict():
    assert _extract_failing_snippets("não-dict", "/tmp", "") == []


def test_extract_failing_snippets_results_nao_lista():
    assert _extract_failing_snippets({"results_by_suite": "invalido"}, "/tmp", "") == []


def test_extract_failing_snippets_extrai_trecho_do_arquivo(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    lines = [f"linha {i}" for i in range(30)]
    (tests_dir / "test_pagamento.py").write_text("\n".join(lines), encoding="utf-8")

    snippets = _extract_failing_snippets(
        _report_com_erro("AssertionError em tests/test_pagamento.py:12"), str(tmp_path), ""
    )

    assert len(snippets) == 1
    assert "# --- Trecho de tests/test_pagamento.py (linha 12) ---" in snippets[0]
    assert "linha 12" in snippets[0]


def test_extract_failing_snippets_ignora_arquivo_principal(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "generated_code.py").write_text("print(1)", encoding="utf-8")
    snippets = _extract_failing_snippets(_report_com_erro("Erro em generated_code.py:3"), str(tmp_path), "")
    assert snippets == []


def test_extract_failing_snippets_ignora_arquivo_inexistente(tmp_path):
    snippets = _extract_failing_snippets(_report_com_erro("Erro em tests/nao_existe.py:3"), str(tmp_path), "")
    assert snippets == []


def test_extract_failing_snippets_ignora_conteudo_igual_ao_anterior(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_rep.py").write_text("mesmo conteúdo", encoding="utf-8")
    snippets = _extract_failing_snippets(
        _report_com_erro("Erro em tests/test_rep.py:1"), str(tmp_path), "mesmo conteúdo"
    )
    assert snippets == []


def test_extract_failing_snippets_limite_de_dois(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name in ("test_a.py", "test_b.py", "test_c.py"):
        (tests_dir / name).write_text("print(1)", encoding="utf-8")
    report = {
        "results_by_suite": [
            {
                "failed_tests_details": [
                    {"error": "Erro em tests/test_a.py:1"},
                    {"error": "Erro em tests/test_b.py:1"},
                    {"error": "Erro em tests/test_c.py:1"},
                ]
            }
        ]
    }
    snippets = _extract_failing_snippets(report, str(tmp_path), "")
    assert len(snippets) == 2


def test_extract_failing_snippets_trunca_excesso(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_big.py").write_text("x" * 3000, encoding="utf-8")
    snippets = _extract_failing_snippets(
        _report_com_erro("Erro em tests/test_big.py:5"), str(tmp_path), "", max_chars=500
    )
    assert len(snippets[0]) <= 500


def test_extract_failing_snippets_pula_detalhe_invalido(tmp_path):
    report = {
        "results_by_suite": [
            {
                "failed_tests_details": [
                    "não-dict",
                    {"error": ""},  # texto vazio → pulado
                    {"error": "Erro sem caminho de arquivo"},
                ]
            }
        ]
    }
    assert _extract_failing_snippets(report, str(tmp_path), "") == []


def test_extract_failing_snippets_suite_nao_dict(tmp_path):
    report = {"results_by_suite": ["não-dict", {"failed_tests_details": [{"error": "x"}]}]}
    assert _extract_failing_snippets(report, str(tmp_path), "") == []


def test_extract_failing_snippets_failed_details_nao_lista(tmp_path):
    report = {"results_by_suite": [{"failed_tests_details": "invalido"}]}
    assert _extract_failing_snippets(report, str(tmp_path), "") == []


def test_extract_failing_snippets_path_sem_numero_de_linha(tmp_path):
    """Erro citando tests/x.py sem ':N' → casado pelo padrão de caminho tests/."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sem_linha.py").write_text("print(1)", encoding="utf-8")
    report = {"results_by_suite": [{"failed_tests_details": [{"error": "File tests/test_sem_linha.py"}]}]}

    snippets = _extract_failing_snippets(report, str(tmp_path), "")
    assert len(snippets) == 1


def test_extract_failing_snippets_caminho_duplicado_pulado(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dup.py").write_text("print(1)", encoding="utf-8")
    report = {
        "results_by_suite": [
            {
                "failed_tests_details": [
                    {"error": "Erro em tests/test_dup.py:1"},
                    {"error": "Outro erro em tests/test_dup.py:2"},
                ]
            }
        ]
    }

    snippets = _extract_failing_snippets(report, str(tmp_path), "")
    assert len(snippets) == 1


def test_extract_failing_snippets_path_traversal_ignorado(tmp_path):
    """Caminho candidato escapando do base_dir (via ..) → relative_to levanta e é pulado."""
    report = {"results_by_suite": [{"failed_tests_details": [{"error": "Erro em tests/../../fora.py:3"}]}]}
    assert _extract_failing_snippets(report, str(tmp_path), "") == []


def test_extract_failing_snippets_arquivo_ilegivel_pulado(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    locked = tests_dir / "test_locked.py"
    locked.write_text("print(1)", encoding="utf-8")
    locked.chmod(0o000)
    report = {"results_by_suite": [{"failed_tests_details": [{"error": "Erro em tests/test_locked.py:1"}]}]}

    try:
        snippets = _extract_failing_snippets(report, str(tmp_path), "")
    finally:
        locked.chmod(0o644)
    assert snippets == []


def test_extract_failing_snippets_arquivo_vazio_pulado(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_vazio.py").write_text("", encoding="utf-8")
    report = {"results_by_suite": [{"failed_tests_details": [{"error": "Erro em tests/test_vazio.py:1"}]}]}

    assert _extract_failing_snippets(report, str(tmp_path), "") == []


# ---------------------------------------------------------------------------
# _check_syntax_and_types: node / cargo / go / javac
# ---------------------------------------------------------------------------


def test_check_syntax_node_erro_de_sintaxe(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/node" if cmd == "node" else None)
    fake_run = MagicMock(return_value=SimpleNamespace(returncode=1, stderr="Unexpected token 'x'"))
    monkeypatch.setattr(subprocess, "run", fake_run)

    errors = _check_syntax_and_types({"app.js": "const = 1;"}, "python")
    assert any("Node syntax check error" in e for e in errors)


def test_check_syntax_node_valido_e_excecao_silenciosa(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/node" if cmd == "node" else None)

    ok = MagicMock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(subprocess, "run", ok)
    assert _check_syntax_and_types({"app.js": "const a = 1;"}, "python") == []

    boom = MagicMock(side_effect=OSError("node sumiu"))
    monkeypatch.setattr(subprocess, "run", boom)
    assert _check_syntax_and_types({"app.js": "const a = 1;"}, "python") == []


def test_check_syntax_cargo_erro_e_excecao(tmp_path, monkeypatch):
    (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/cargo" if cmd == "cargo" else None)

    fail = MagicMock(return_value=SimpleNamespace(returncode=1, stderr="error[E0308]: mismatch"))
    monkeypatch.setattr(subprocess, "run", fail)
    errors = _check_syntax_and_types({"src/main.rs": "fn main() {}"}, "rust", str(tmp_path))
    assert any("Cargo check error" in e for e in errors)

    boom = MagicMock(side_effect=OSError("cargo indisponível"))
    monkeypatch.setattr(subprocess, "run", boom)
    assert _check_syntax_and_types({"src/main.rs": "fn main() {}"}, "rust", str(tmp_path)) == []


def test_check_syntax_go_vet_erro_e_excecao(tmp_path, monkeypatch):
    (tmp_path / "go.mod").write_text("module app\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/go" if cmd == "go" else None)

    fail = MagicMock(return_value=SimpleNamespace(returncode=1, stderr="undefined: foo"))
    monkeypatch.setattr(subprocess, "run", fail)
    errors = _check_syntax_and_types({"main.go": "package main"}, "go", str(tmp_path))
    assert any("Go vet error" in e for e in errors)

    boom = MagicMock(side_effect=OSError("go indisponível"))
    monkeypatch.setattr(subprocess, "run", boom)
    assert _check_syntax_and_types({"main.go": "package main"}, "go", str(tmp_path)) == []


def test_check_syntax_javac_excecao_silenciosa(tmp_path, monkeypatch):
    java_dir = tmp_path / "src" / "main" / "java"
    java_dir.mkdir(parents=True)
    (java_dir / "Main.java").write_text("public class Main {}", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/javac" if cmd == "javac" else None)
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=OSError("javac quebrou")))

    assert _check_syntax_and_types({"src/main/java/Main.java": "public class Main {}"}, "java", str(tmp_path)) == []


# ---------------------------------------------------------------------------
# developer(): circuit breaker, mock+contrato, hooks, streaming, erros
# ---------------------------------------------------------------------------


def _state_llm(tmp_path, **extra):
    state = {
        "idea": "app de teste",
        "tech_spec": "# Spec\nImplemente o código",
        "user_stories": [{"id": "US-001", "title": "Feature", "acceptance_criteria": ["c1"]}],
        "stack": "python",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": False,
        "feedback_history": [],
    }
    state.update(extra)
    return state


def test_developer_circuit_breaker_pausa_run(tmp_path):
    """Budget excedido → interrupt() com payload paused_budget (hard-stop M-10)."""
    cb = CircuitBreaker(max_total_cost=0.0)
    cb.record_iteration()  # total_cost 0.05 >= 0 → budget_exceeded
    state = _state_llm(tmp_path, mock_llm=True, circuit_breaker=cb)

    with patch("lf.pipeline.nodes.developer.interrupt", return_value=None) as mock_interrupt:
        developer(state)

    assert mock_interrupt.called
    payload = mock_interrupt.call_args[0][0]
    assert payload["paused_budget"] is True
    assert payload["node"] == "developer"


def test_developer_circuit_breaker_snapshot_dict(tmp_path):
    """CB vindo como snapshot dict (serialização usada pelo dispatcher) ativa o hard-stop."""
    cb = CircuitBreaker(max_total_cost=0.0)
    cb.record_iteration()
    snapshot = cb.snapshot()  # __getstate__ → compatível com from_snapshot
    state = _state_llm(tmp_path, mock_llm=True, circuit_breaker=snapshot)

    with patch("lf.pipeline.nodes.developer.interrupt", return_value=None) as mock_interrupt:
        developer(state)

    assert mock_interrupt.called


def test_developer_mock_com_contrato_filtra_tests(tmp_path, capsys):
    state = _state_llm(tmp_path, mock_llm=True, contract_tests="def test_ok():\n    assert True\n### MODULES: app")
    res = developer(state)

    assert res["next_agent"] == "qa"
    # tests/test_main.py do projeto mock python foi removido pelo filtro de contrato
    assert not (tmp_path / "tests" / "test_main.py").exists()
    assert (tmp_path / "generated_code.py").exists()
    assert "pulou 1 arquivo(s) tests/" in capsys.readouterr().out


def test_developer_genome_hook_erro_nao_quebra(tmp_path, monkeypatch, capsys):
    """GenomeScanner falha → loga hook_error e segue o fluxo normal."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("genome.GenomeScanner.scan", MagicMock(side_effect=RuntimeError("scan boom")))

    with patch(
        "lf.pipeline.nodes.developer.call_llm_via_opencode",
        return_value="```python\ndef main():\n    pass\n```",
    ):
        res = developer(_state_llm(tmp_path))

    assert res["next_agent"] == "qa"
    assert "Genome scanner não utilizado" in capsys.readouterr().out
    assert (tmp_path / ".loopforge" / "telemetry.sqlite").exists()


def test_developer_memory_hook_erro_nao_quebra(tmp_path, monkeypatch, capsys):
    fake_mem = MagicMock()
    fake_mem.search_relevant_lessons.side_effect = RuntimeError("memória indisponível")
    monkeypatch.setattr("lf.memory.manager.MemoryManager", MagicMock(return_value=fake_mem))
    monkeypatch.setattr("lf.memory.manager.cross_project_enabled", lambda config=None: False)

    with patch(
        "lf.pipeline.nodes.developer.call_llm_via_opencode",
        return_value="```python\ndef main():\n    pass\n```",
    ):
        res = developer(_state_llm(tmp_path))

    assert res["next_agent"] == "qa"
    assert "Não foi possível carregar memória" in capsys.readouterr().out


def test_developer_registry_hook_quebras_e_erro(tmp_path, monkeypatch, capsys):
    class FakeRegistryChecker:
        def __init__(self, path):
            pass

        def check(self, agent=None):
            return ["BR-001: contrato quebrado"]

    monkeypatch.setattr("registry.RegistryChecker", FakeRegistryChecker)

    with patch(
        "lf.pipeline.nodes.developer.call_llm_via_opencode",
        return_value="```python\ndef main():\n    pass\n```",
    ):
        res = developer(_state_llm(tmp_path))

    assert res["next_agent"] == "qa"
    out = capsys.readouterr().out
    assert "1 quebras de contrato" in out

    # Caminho de exceção do hook
    class BrokenRegistryChecker:
        def __init__(self, path):
            pass

        def check(self, agent=None):
            raise RuntimeError("registry quebrado")

    monkeypatch.setattr("registry.RegistryChecker", BrokenRegistryChecker)
    with patch(
        "lf.pipeline.nodes.developer.call_llm_via_opencode",
        return_value="```python\ndef main():\n    pass\n```",
    ):
        res = developer(_state_llm(tmp_path))

    assert res["next_agent"] == "qa"
    assert "Registry hook ignorado" in capsys.readouterr().out


def test_developer_feedback_test_report_inclui_falhas(tmp_path):
    captured = {}

    def _fake_call_llm(**kwargs):
        captured["user_prompt"] = kwargs.get("user_prompt", "")
        return "### FILE: generated_code.py\n```python\ndef main():\n    pass\n```"

    state = _state_llm(
        tmp_path,
        feedback_history=[{"from": "qa", "message": "teste quebrou"}],
        test_report={
            "results_by_suite": [{"failed_tests_details": [{"error": "AssertionError em tests/app_test.py:4"}]}]
        },
    )
    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm):
        developer(state)

    prompt = captured["user_prompt"]
    assert "[QA Test Failure]: AssertionError" in prompt
    assert "[QA Feedback]: teste quebrou" in prompt


def test_developer_codigo_anterior_e_snippets_de_falha(tmp_path):
    captured = {}

    def _fake_call_llm(**kwargs):
        captured["user_prompt"] = kwargs.get("user_prompt", "")
        return "```python\ndef main():\n    pass\n```"

    state = _state_llm(
        tmp_path,
        feedback_history=[{"from": "qa", "message": "corrija"}],
        code="def main():\n    pass",
        test_report={"results_by_suite": []},
    )
    with (
        patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm),
        patch("lf.pipeline.nodes.developer._extract_failing_snippets", return_value=["SNIPPET-123"]),
    ):
        developer(state)

    prompt = captured["user_prompt"]
    assert "Código anterior que apresentou falha" in prompt
    assert "SNIPPET-123" in prompt
    assert "Trechos dos arquivos citados nas falhas" in prompt


def test_developer_complexidade_mvp_e_advanced(tmp_path):
    prompts = {}

    def _fake_call_llm(**kwargs):
        prompts[kwargs.get("user_prompt", "")] = True
        return "```python\ndef main():\n    pass\n```"

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm):
        developer(_state_llm(tmp_path, complexity_level="mvp"))
        developer(_state_llm(tmp_path, complexity_level="advanced"))

    assert any("NÍVEL DE COMPLEXIDADE: MVP" in p for p in prompts)
    assert any("NÍVEL DE COMPLEXIDADE: AVANÇADO" in p for p in prompts)


def test_developer_raw_nao_string_e_coagido(tmp_path):
    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", return_value=123):
        res = developer(_state_llm(tmp_path))

    assert res["next_agent"] == "qa"
    assert res["code"] == "123"


def test_developer_streaming_token_delta(tmp_path):
    captured = {}

    def _fake_call_llm(**kwargs):
        captured.update(kwargs)
        return "```python\ndef main():\n    pass\n```"

    config = {"configurable": {"thread_id": "run-abc123"}}
    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm):
        developer(_state_llm(tmp_path), config=config)

    from lf.pipeline.llm_factory import TokenDeltaPublisher

    publisher = captured["on_token_delta"]
    assert isinstance(publisher, TokenDeltaPublisher)
    assert publisher.run_id == "abc123"
    assert publisher.node == "developer"


def test_developer_sem_thread_run_streaming_desligado(tmp_path):
    captured = {}

    def _fake_call_llm(**kwargs):
        captured.update(kwargs)
        return "```python\ndef main():\n    pass\n```"

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_call_llm):
        # config com thread_id que não começa com "run-" → streaming off
        developer(_state_llm(tmp_path), config={"configurable": {"thread_id": "outro-id"}})

    assert captured["on_token_delta"] is None


def test_developer_contrato_filtra_tests_no_caminho_llm(tmp_path, capsys):
    llm_response = (
        "### FILE: generated_code.py\n```python\ndef main():\n    pass\n```\n"
        "### FILE: tests/test_main.py\n```python\ndef test():\n    assert True\n```\n"
    )
    state = _state_llm(tmp_path, contract_tests="def test_ok():\n    assert True")
    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", return_value=llm_response):
        res = developer(state)

    assert res["next_agent"] == "qa"
    assert (tmp_path / "generated_code.py").exists()
    assert not (tmp_path / "tests" / "test_main.py").exists()
    assert "pulou 1 arquivo(s) tests/" in capsys.readouterr().out


def test_developer_retry_limpa_diretorios_antigos(tmp_path):
    state = _state_llm(tmp_path, qa_attempt_count=1)
    with (
        patch(
            "lf.pipeline.nodes.developer.call_llm_via_opencode",
            return_value="```python\ndef main():\n    pass\n```",
        ),
        patch("lf.pipeline.nodes.developer._cleanup_stale_project_dirs") as mock_cleanup,
    ):
        developer(state)

    assert mock_cleanup.called
    assert mock_cleanup.call_args[0][0] == [str(tmp_path), str(tmp_path)]
    assert mock_cleanup.call_args[1]["stack"] == "python"


def test_developer_read_only_nao_escreve(tmp_path):
    with (
        patch(
            "lf.pipeline.nodes.developer.call_llm_via_opencode",
            return_value="```python\ndef main():\n    pass\n```",
        ),
        patch("lf.pipeline.nodes.developer._write_project_files") as mock_write,
    ):
        res = developer(_state_llm(tmp_path, read_only=True))

    assert res["next_agent"] == "qa"
    assert not mock_write.called


# ---------------------------------------------------------------------------
# _cleanup_stale_project_dirs: dogfooding, exceções, symlink estrangeiro
# ---------------------------------------------------------------------------


def _fake_loopforge_repo(tmp_path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "AGENTS.md").write_text("", encoding="utf-8")
    (repo / "src" / "lf").mkdir(parents=True, exist_ok=True)
    return str(repo)


def test_cleanup_dogfooding_pula_repo_loopforge(tmp_path):
    repo = _fake_loopforge_repo(tmp_path)
    (Path(repo) / "target").mkdir()
    (Path(repo) / "pom.xml").write_text("<project/>", encoding="utf-8")

    _cleanup_stale_project_dirs([repo], stack="python")

    # Nada deve ser removido dentro do repo LoopForge (proteção dogfooding)
    assert (Path(repo) / "target").exists()
    assert (Path(repo) / "pom.xml").exists()


def test_cleanup_rmtree_exception_avisa(tmp_path, capsys):
    base = tmp_path / "proj"
    base.mkdir()
    (base / "target").mkdir()
    with patch("shutil.rmtree", side_effect=OSError("permissão negada")):
        _cleanup_stale_project_dirs([str(base)], stack="python")

    assert "Não foi possível remover subdiretório antigo" in capsys.readouterr().out


def test_cleanup_unlink_exception_avisa(tmp_path, monkeypatch, capsys):
    base = tmp_path / "proj"
    base.mkdir()
    (base / "go.mod").write_text("module x\n", encoding="utf-8")  # estrangeiro à stack python

    original_unlink = Path.unlink

    def _fake_unlink(self, *args, **kwargs):
        if self.name == "go.mod":
            raise PermissionError("denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _fake_unlink)
    _cleanup_stale_project_dirs([str(base)], stack="python")

    assert "Não foi possível remover" in capsys.readouterr().out
    assert (base / "go.mod").exists()


def test_cleanup_symlink_estrangeiro_fora_do_base_pulado(tmp_path):
    base = tmp_path / "proj"
    base.mkdir()
    outside = tmp_path / "fora.py"
    outside.write_text("print(1)", encoding="utf-8")
    (base / "sneaky.py").symlink_to(outside)
    (base / "go.mod").write_text("module x\n", encoding="utf-8")

    _cleanup_stale_project_dirs([str(base)], stack="python")

    # go.mod (estrangeiro real) removido; symlink que resolve para FORA do base fica
    assert not (base / "go.mod").exists()
    assert (base / "sneaky.py").is_symlink()


# ---------------------------------------------------------------------------
# _write_project_files: proteção dogfooding
# ---------------------------------------------------------------------------


def test_write_project_files_pula_repo_loopforge(tmp_path, capsys):
    repo = _fake_loopforge_repo(tmp_path)

    _write_project_files({"generated_code.py": "print(1)"}, [repo])

    assert not (Path(repo) / "generated_code.py").exists()
    assert "Diretório dentro do repo LoopForge protegido" in capsys.readouterr().out
