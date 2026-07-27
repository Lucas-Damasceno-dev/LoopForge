import json
from pathlib import Path
from typing import Any


class MemoryManager:
    def __init__(self, memory_file: str | Path = ".loopforge/memory.json"):
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def save(self, data: dict[str, Any]):
        self.memory_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update_key(self, key: str, value: Any):
        mem = self.load()
        mem[key] = value
        self.save(mem)
