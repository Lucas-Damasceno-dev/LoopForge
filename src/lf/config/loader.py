import json
from pathlib import Path
from typing import Any, Union
import yaml

from lf.config.schema import LoopForgeConfig


def load_config(config_path: Union[str, Path] = ".loopforge.json") -> LoopForgeConfig:
    path = Path(config_path)
    if not path.exists():
        # Fallback to yaml if json not found
        yaml_path = path.with_suffix(".yaml")
        if yaml_path.exists():
            path = yaml_path
        else:
            return LoopForgeConfig()

    content = path.read_text(encoding="utf-8")
    if path.suffix in [".yaml", ".yml"]:
        data = yaml.safe_load(content) or {}
    else:
        data = json.loads(content)

    return LoopForgeConfig(**data)


def save_config(config: LoopForgeConfig, config_path: Union[str, Path] = ".loopforge.json") -> Path:
    path = Path(config_path)
    data = config.model_dump(mode="json")
    if path.suffix in [".yaml", ".yml"]:
        path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
