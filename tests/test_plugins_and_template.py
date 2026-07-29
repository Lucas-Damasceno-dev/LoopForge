"""Testes do carregador de templates HTML e diretório contrib."""

from pathlib import Path

from lf.api.dashboard_html import get_dashboard_html


def test_contrib_directory_removed():
    contrib_path = Path("src/lf/contrib")
    assert not contrib_path.exists() or not (contrib_path / "api").exists()


def test_dashboard_template_loading():
    html = get_dashboard_html()
    assert "LoopForge v6" in html
    assert "<!DOCTYPE html>" in html
