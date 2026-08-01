"""Interfaces abstratas dos repositórios."""

from abc import ABC, abstractmethod
from typing import Any

from app.models.entities import Expense, Group, Participant

class GroupRepository(ABC):
    """Interface do repositório de grupos."""

    @abstractmethod
    def create(self, group: Group) -> Group:
        """Persiste um novo grupo."""
        raise NotImplementedError

    @abstractmethod
    def get(self, group_id: Any) -> Group | None:
        """Busca um grupo pelo identificador."""
        raise NotImplementedError

    @abstractmethod
    def add_participant(self, group_id: Any, participant: Participant) -> Participant:
        """Persiste um participante em um grupo."""
        raise NotImplementedError

class ExpenseRepository(ABC):
    """Interface do repositório de despesas."""

    @abstractmethod
    def create(self, expense: Expense) -> Expense:
        """Persiste uma nova despesa."""
        raise NotImplementedError

    @abstractmethod
    def list_by_group(self, group_id: Any) -> list[Expense]:
        """Lista despesas de um grupo."""
        raise NotImplementedError