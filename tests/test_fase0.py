from pathlib import Path

from lf.config.loader import load_config, save_config
from lf.config.schema import LoopForgeConfig, TechStack


def test_config_load_and_save(tmp_path: Path):
    cfg_file = tmp_path / ".loopforge.json"
    cfg = LoopForgeConfig(project_name="Test Project", stack=TechStack(language="python"))
    save_config(cfg, cfg_file)

    assert cfg_file.exists()
    loaded = load_config(cfg_file)
    assert loaded.project_name == "Test Project"
    assert loaded.stack.language == "python"
