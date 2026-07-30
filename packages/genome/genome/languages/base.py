"""Interface abstrata para scanners de linguagem."""

from abc import ABC, abstractmethod
from genome.store.models import ModuleInfo


class BaseLanguageScanner(ABC):
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Nome da linguagem (ex: 'python', 'typescript')."""
        pass

    @property
    @abstractmethod
    def extensions(self) -> list[str]:
        """Extensões de arquivo suportadas (ex: ['.py'], ['.ts', '.tsx'])."""
        pass

    def can_handle(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.extensions)

    @abstractmethod
    def scan_file(self, file_path: str, code: str) -> ModuleInfo:
        """Examina o código do arquivo e retorna ModuleInfo com exports, imports e contagens."""
        pass
