"""Testes de validação para Decisão de Stack pelo Tech Lead, lessons.md e lf pr."""
from click.testing import CliRunner

from lf.cli.commands.pr import create_git_pr, pr_cmd
from lf.pipeline.nodes.developer import developer
from lf.pipeline.nodes.lessons import generate_lessons_md
from lf.pipeline.nodes.qa import qa
from lf.pipeline.nodes.tech_lead import tech_lead


def test_tech_lead_decides_stack_dynamically(tmp_path):
    state = {
        "idea": "CLI em Rust que lê arquivos CSV e gera relatórios em JSON",
        "user_stories": [{"id": "US-001", "title": "Ler CSV em Rust", "epic_id": "E-001"}],
        "mock_llm": True,
        "stack": None,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res_tl = tech_lead(state)
    assert res_tl["stack"] is not None
    assert "rust" in res_tl["stack"].lower()

    # Developer usa a stack decidida pelo TL
    res_dev = developer(res_tl)
    assert res_dev["code"] is not None

    # QA detecta os arquivos Rust gerados automaticamente
    res_qa = qa(res_dev)
    assert res_qa["test_report"] is not None


def test_user_stack_override():
    state = {
        "idea": "API em Flask",
        "user_stories": [{"id": "US-001", "title": "Endpoint Flask", "epic_id": "E-001"}],
        "mock_llm": True,
        "stack": "python",  # Override manual da CLI
    }
    res_tl = tech_lead(state)
    assert res_tl["stack"] == "python"


def test_lessons_md_artifact_generation(tmp_path):
    state = {
        "idea": "API REST em Go",
        "stack": "go",
        "attempt_count": 1,
        "test_report": {"summary": {"tests_passed": 5, "tests_failed": 0, "total_tests": 5}},
        "security_review": {"status": "PASS", "vulnerabilities_found": []},
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    content = generate_lessons_md(state)
    assert "# 📋 LoopForge Execution Lessons & Report" in content
    assert "Stack Decidida pelo Tech Lead:** `go`" in content
    assert (tmp_path / "lessons.md").exists()


def test_git_init_and_commit_pr(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    res = create_git_pr(project_dir=str(tmp_path), idea="Test PR Feature", session_id="test1234")
    assert res["status"] == "success"
    assert (tmp_path / ".git").exists()

    runner = CliRunner()
    cli_res = runner.invoke(pr_cmd, ["--dir", str(tmp_path), "--idea", "CLI Test PR"])
    assert cli_res.exit_code == 0
