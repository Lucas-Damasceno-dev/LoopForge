"""Interface abstrata para Symbol Resolvers."""

from abc import ABC, abstractmethod
from typing import List, Set
from genome.store.models import ModuleInfo


class BaseSymbolResolver(ABC):
    @abstractmethod
    def resolve_dependencies(
        self, module: ModuleInfo, repo_root: str, known_files: Set[str]
    ) -> List[str]:
        """Resolve importações brutas para caminhos de arquivos de dependência reais do repositório."""
        pass
