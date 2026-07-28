import pytest
import json
from pathlib import Path
from lf.memory.manager import MemoryManager


def test_memory_manager(tmp_path):
    mem_file = tmp_path / "memory.json"
    manager = MemoryManager(memory_file=mem_file)

    # Test load non-existing
    assert manager.load() == {}

    # Test save and load
    data = {"last_task": "T-001", "lessons": ["Always check types"]}
    manager.save(data)
    assert manager.load() == data

    # Test update_key
    manager.update_key("status", "completed")
    updated = manager.load()
    assert updated["status"] == "completed"
    assert updated["last_task"] == "T-001"

    # Test corrupted JSON fallback
    mem_file.write_text("corrupted json {{{", encoding="utf-8")
    assert manager.load() == {}
