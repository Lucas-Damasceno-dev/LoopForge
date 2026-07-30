"""Checker de contratos de interface e busca de quebras."""

from typing import List, Optional
from registry.core.analyzer import check_breaking_changes
from registry.core.scanner import InterfaceScanner
from registry.store.models import BreakingChange, InterfaceItem, RegistrySchema
from registry.store.sqlite import RegistryStore


class RegistryChecker:
    def __init__(self, repo_root: str):
        self.repo_root = repo_root

    def check(self, agent: Optional[str] = None) -> List[BreakingChange]:
        store = RegistryStore(self.repo_root)
        old_schema = store.load()

        scanner = InterfaceScanner(self.repo_root)
        new_schema = scanner.scan(current_agent=agent or "developer")

        if not old_schema:
            store.save(new_schema)
            return []

        breaking = check_breaking_changes(old_schema, new_schema)
        new_schema.breaking_changes = breaking
        store.save(new_schema)

        if agent:
            return [b for b in breaking if any(c.agent == agent for c in b.impacted_consumers)]

        return breaking

    def uncovered_interfaces(self) -> List[InterfaceItem]:
        store = RegistryStore(self.repo_root)
        schema = store.load()
        if not schema:
            scanner = InterfaceScanner(self.repo_root)
            schema = scanner.scan()

        uncovered = []
        for item in schema.interfaces:
            has_test_consumer = any("test" in c.file.lower() for c in item.consumers)
            if not has_test_consumer:
                uncovered.append(item)

        return uncovered
