"""Interface abstrata para Notifiers de quebra de contrato."""

from abc import ABC, abstractmethod
from typing import List
from registry.store.models import BreakingChange


class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, breaking_changes: List[BreakingChange]) -> None:
        pass
