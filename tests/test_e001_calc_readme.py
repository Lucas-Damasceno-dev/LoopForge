"""US009 — Documentação básica de uso (README)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


def _readme() -> str:
    assert README.exists(), "README.md ausente na raiz do projeto"
    return README.read_text(encoding="utf-8")


def test_us009_readme_instalacao_com_pip():
    readme = _readme()
    assert "pip install" in readme
    assert "pip install lf" in readme or "pip install ." in readme or "pip install -e ." in readme


def test_us009_readme_exemplos_de_uso():
    readme = _readme()
    assert "calc" in readme
    assert "%" in readme
    assert "convert" in readme


def test_us009_readme_solucao_de_problemas():
    readme = _readme()
    assert "problema" in readme.lower() or "troubleshoot" in readme.lower()
    assert "erro" in readme.lower()
