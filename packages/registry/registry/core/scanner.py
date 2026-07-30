"""Scanner de interfaces exportadas e busca de consumidores no codebase."""

from datetime import datetime, timezone
import os
import re
from typing import Dict, List, Set
from registry.store.models import ConsumerInfo, InterfaceHistory, InterfaceItem, RegistrySchema


class InterfaceScanner:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)

    def _should_ignore(self, rel_path: str) -> bool:
        ignore_dirs = {
            ".git",
            ".registry",
            ".genome",
            ".loopforge",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            "dist",
            "build",
        }
        parts = rel_path.split(os.sep)
        return any(p in ignore_dirs for p in parts)

    def scan(self, current_agent: str = "developer") -> RegistrySchema:
        interfaces: List[InterfaceItem] = []
        file_contents: Dict[str, str] = {}

        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.relpath(os.path.join(root, d), self.repo_root))]
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.repo_root)
                if not self._should_ignore(rel_path) and rel_path.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                            file_contents[rel_path] = file_obj.read()
                    except Exception:
                        pass

        # 1. Extrair interfaces exportadas por arquivo
        # Regex Python def name(...)
        py_def_regex = re.compile(r"""def\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)""")
        # Regex JS/TS export function / class / const
        ts_func_regex = re.compile(r"""export\s+(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)""")
        ts_class_regex = re.compile(r"""export\s+(?:abstract\s+)?class\s+([A-Za-z0-9_$]+)""")

        now_iso = datetime.now(timezone.utc).isoformat()

        for rel_path, code in file_contents.items():
            lines = code.splitlines()

            if rel_path.endswith(".py"):
                for line_idx, line in enumerate(lines, start=1):
                    line_str = line.strip()
                    m = py_def_regex.search(line_str)
                    if m:
                        name = m.group(1)
                        if not name.startswith("_"):
                            sig = f"({m.group(2).strip()})"
                            item_id = f"{rel_path}:{name}"
                            interfaces.append(
                                InterfaceItem(
                                    id=item_id,
                                    kind="function",
                                    name=name,
                                    module=rel_path,
                                    signature=sig,
                                    exported=True,
                                    last_modified=now_iso,
                                    last_agent=current_agent,
                                    history=[InterfaceHistory(signature=sig, agent=current_agent)],
                                )
                            )
            elif rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                for line_idx, line in enumerate(lines, start=1):
                    line_str = line.strip()
                    if not line_str.startswith("export"):
                        continue
                    m = ts_func_regex.search(line_str)
                    if m:
                        name = m.group(1)
                        sig = f"({m.group(2).strip()})"
                        item_id = f"{rel_path}:{name}"
                        interfaces.append(
                            InterfaceItem(
                                id=item_id,
                                kind="function",
                                name=name,
                                module=rel_path,
                                signature=sig,
                                exported=True,
                                last_modified=now_iso,
                                last_agent=current_agent,
                                history=[InterfaceHistory(signature=sig, agent=current_agent)],
                            )
                        )
                        continue

                    m = ts_class_regex.search(line_str)
                    if m:
                        name = m.group(1)
                        item_id = f"{rel_path}:{name}"
                        interfaces.append(
                            InterfaceItem(
                                id=item_id,
                                kind="class",
                                name=name,
                                module=rel_path,
                                signature=f"class {name}",
                                exported=True,
                                last_modified=now_iso,
                                last_agent=current_agent,
                                history=[InterfaceHistory(signature=f"class {name}", agent=current_agent)],
                            )
                        )

        # 2. Identificar consumidores para cada interface
        for item in interfaces:
            item_name = item.name
            consumers: List[ConsumerInfo] = []
            for file_path, code in file_contents.items():
                if file_path == item.module:
                    continue
                # Se o nome da interface for mencionado no código de outro arquivo
                if item_name in code:
                    # Determinar linha e agente provável
                    for line_idx, line in enumerate(code.splitlines(), start=1):
                        if item_name in line:
                            agent_type = "qa" if "test" in file_path.lower() else "developer"
                            consumers.append(ConsumerInfo(file=file_path, line=line_idx, agent=agent_type))

            item.consumers = consumers

        return RegistrySchema(version="1.0.0", interfaces=interfaces)
