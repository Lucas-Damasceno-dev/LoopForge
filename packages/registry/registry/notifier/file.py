"""Notificador em arquivo JSON local."""

import json
import os
from typing import List
from registry.notifier.base import BaseNotifier
from registry.store.models import BreakingChange


class FileNotifier(BaseNotifier):
    def __init__(self, output_path: str):
        self.output_path = output_path

    def notify(self, breaking_changes: List[BreakingChange]) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)
        data = [bc.model_dump() for bc in breaking_changes]
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
