"""Testes de cobertura para o comando lf diff."""

from __future__ import annotations

import subprocess

from rich.console import Console

from lf.cli.commands import diff as diff_module


class _FakeResult:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0


def _run_diff(project_id: str, target_dir: str, interactive: bool):
    diff_module.diff_cmd.callback(  # type: ignore[attr-defined]
        project_id=project_id,
        target_dir=target_dir,
        interactive=interactive,
    )


def test_git_fallback_stdout_non_interactive(monkeypatch, tmp_path):
    out = []
    monkeypatch.setattr(diff_module, "console", Console(record=True))

    def fake_run(*args, **kwargs):
        out.append((args, kwargs))
        return _FakeResult("diff --git a/a.py b/a.py\n+print('ok')\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _run_diff(project_id="not-found-1", target_dir=str(tmp_path), interactive=False)
    rendered = diff_module.console.export_text()
    assert "Analisando alterações propostas" in rendered
    assert "Nenhuma alteração temporária" not in rendered
    assert out and out[0][1]["timeout"] == 5


def test_git_fallback_stdout_interactive(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult("diff --git a/x b/x\n"))
    called = {"count": 0}

    def fake_render(title: str, diff_text: str):
        called["count"] += 1
        assert title == "Git Workspace Diff"
        assert "diff --git" in diff_text

    monkeypatch.setattr(diff_module, "_render_side_by_side_diff", fake_render)
    _run_diff(project_id="not-found-2", target_dir=str(tmp_path), interactive=True)
    assert called["count"] == 1


def test_git_fallback_stdout_empty_shows_yellow(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult(""))
    _run_diff(project_id="not-found-3", target_dir=str(tmp_path), interactive=False)
    assert "Nenhuma alteração temporária encontrada" in diff_module.console.export_text()


def test_git_fallback_error_shows_yellow(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))

    def fake_run(*_a, **_k):
        raise RuntimeError("git indisponível")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _run_diff(project_id="not-found-4", target_dir=str(tmp_path), interactive=False)
    assert "Nenhuma alteração temporária encontrada" in diff_module.console.export_text()


def test_proposed_dir_equal_files_shows_green(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))
    project_id = "proj-equal"
    proposed = tmp_path / "loopforge" / project_id
    target = tmp_path / "workspace"
    proposed.mkdir(parents=True)
    target.mkdir()
    (proposed / "same.py").write_text("print('igual')\n")
    (target / "same.py").write_text("print('igual')\n")
    monkeypatch.setattr(diff_module, "Path", lambda p: proposed if str(p).startswith("/tmp/loopforge/") else p)
    _run_diff(project_id=project_id, target_dir=str(target), interactive=False)
    assert "Nenhuma diferença encontrada entre os arquivos propostos e o workspace." in diff_module.console.export_text()


def test_proposed_dir_diff_and_new_file_non_interactive(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))
    project_id = "proj-diff"
    proposed = tmp_path / "loopforge" / project_id
    target = tmp_path / "workspace"
    proposed.mkdir(parents=True)
    target.mkdir()
    (proposed / "changed.py").write_text("print('novo')\n")
    (target / "changed.py").write_text("print('antigo')\n")
    (proposed / "new_file.py").write_text("print('arquivo novo')\n")
    monkeypatch.setattr(diff_module, "Path", lambda p: proposed if str(p).startswith("/tmp/loopforge/") else p)
    _run_diff(project_id=project_id, target_dir=str(target), interactive=False)
    rendered = diff_module.console.export_text()
    assert "📄 changed.py:" in rendered
    assert "📄 new_file.py:" in rendered


def test_proposed_dir_interactive_uses_side_by_side_files(monkeypatch, tmp_path):
    monkeypatch.setattr(diff_module, "console", Console(record=True))
    project_id = "proj-int"
    proposed = tmp_path / "loopforge" / project_id
    target = tmp_path / "workspace"
    proposed.mkdir(parents=True)
    target.mkdir()
    (proposed / "mod.py").write_text("print('A')\n")
    (target / "mod.py").write_text("print('B')\n")
    monkeypatch.setattr(diff_module, "Path", lambda p: proposed if str(p).startswith("/tmp/loopforge/") else p)
    calls = []
    monkeypatch.setattr(
        diff_module,
        "_render_side_by_side_files",
        lambda filename, original, proposed: calls.append((filename, original, proposed)),
    )
    _run_diff(project_id=project_id, target_dir=str(target), interactive=True)
    assert len(calls) == 1
    assert calls[0][0] == "mod.py"
