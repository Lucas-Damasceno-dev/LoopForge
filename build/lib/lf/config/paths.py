"""Centralização de caminhos e constantes de diretório do LoopForge."""
from pathlib import Path

LOOPFORGE_DIR = Path(".loopforge")
TRAJECTORIES_DB_PATH = LOOPFORGE_DIR / "trajectories.db"
LLM_CACHE_DB_PATH = LOOPFORGE_DIR / "llm_cache.sqlite"
TELEMETRY_DB_PATH = LOOPFORGE_DIR / "telemetry.sqlite"
LESSONS_PATH = LOOPFORGE_DIR / "lessons.md"
HANDOFF_PATH = LOOPFORGE_DIR / "handoff.md"


def get_loopforge_dir(base_dir: str | Path = ".") -> Path:
    p = Path(base_dir) / ".loopforge"
    p.mkdir(parents=True, exist_ok=True)
    return p
