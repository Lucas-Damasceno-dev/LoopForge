"""Carregador de templates HTML para o Web Dashboard UI do LoopForge."""

from functools import lru_cache
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"
DASHBOARD_FILE = TEMPLATES_DIR / "dashboard.html"


@lru_cache
def get_dashboard_html() -> str:
    """Carrega o conteúdo HTML do template dashboard.html com cache."""
    if DASHBOARD_FILE.exists():
        return DASHBOARD_FILE.read_text(encoding="utf-8")
    return "<html><body><h1>LoopForge Dashboard Template Not Found</h1></body></html>"


# Exporta constante para compatibilidade retroativa
DASHBOARD_HTML = get_dashboard_html()
