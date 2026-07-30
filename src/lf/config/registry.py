"""Registry pattern para TechStackHandlers.
Desacopla a resolução de linguagens, ferramentas de teste e gerenciadores de pacote do core.
"""

from abc import ABC, abstractmethod
import os
from typing import Dict, Optional, Type
from pydantic import BaseModel


class BaseStackHandler(ABC):
    @property
    @abstractmethod
    def language(self) -> str:
        pass

    @property
    @abstractmethod
    def default_framework(self) -> str:
        pass

    @property
    @abstractmethod
    def default_test_harness(self) -> str:
        pass

    @property
    @abstractmethod
    def default_package_manager(self) -> str:
        pass

    @abstractmethod
    def detect_test_command(self, project_dir: str) -> Optional[str]:
        pass


class PythonStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "python"

    @property
    def default_framework(self) -> str:
        return "fastapi"

    @property
    def default_test_harness(self) -> str:
        return "pytest"

    @property
    def default_package_manager(self) -> str:
        return "pip"

    def detect_test_command(self, project_dir: str) -> Optional[str]:
        if os.path.exists(os.path.join(project_dir, "pyproject.toml")) or any(
            f.endswith(".py") for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f))
        ):
            return "pytest"
        return None


class JavaStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "java"

    @property
    def default_framework(self) -> str:
        return "spring-boot"

    @property
    def default_test_harness(self) -> str:
        return "junit"

    @property
    def default_package_manager(self) -> str:
        return "maven"

    def detect_test_command(self, project_dir: str) -> Optional[str]:
        if os.path.exists(os.path.join(project_dir, "pom.xml")):
            return "mvn test"
        if os.path.exists(os.path.join(project_dir, "build.gradle")):
            return "./gradlew test"
        return None


class RustStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "rust"

    @property
    def default_framework(self) -> str:
        return "actix"

    @property
    def default_test_harness(self) -> str:
        return "cargotest"

    @property
    def default_package_manager(self) -> str:
        return "cargo"

    def detect_test_command(self, project_dir: str) -> Optional[str]:
        if os.path.exists(os.path.join(project_dir, "Cargo.toml")):
            return "cargo test"
        return None


class GoStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "go"

    @property
    def default_framework(self) -> str:
        return "gin"

    @property
    def default_test_harness(self) -> str:
        return "gotest"

    @property
    def default_package_manager(self) -> str:
        return "go"

    def detect_test_command(self, project_dir: str) -> Optional[str]:
        if os.path.exists(os.path.join(project_dir, "go.mod")):
            return "go test ./..."
        return None


class JSStackHandler(BaseStackHandler):
    @property
    def language(self) -> str:
        return "javascript"

    @property
    def default_framework(self) -> str:
        return "express"

    @property
    def default_test_harness(self) -> str:
        return "vitest"

    @property
    def default_package_manager(self) -> str:
        return "npm"

    def detect_test_command(self, project_dir: str) -> Optional[str]:
        pkg_path = os.path.join(project_dir, "package.json")
        if os.path.exists(pkg_path):
            if os.path.exists(os.path.join(project_dir, "vitest.config.ts")) or os.path.exists(os.path.join(project_dir, "vitest.config.js")):
                return "npx vitest run"
            return "npm test"
        return None


class TechStackRegistry:
    """Registro global extensível para manipuladores de linguagem/stack."""
    _handlers: Dict[str, BaseStackHandler] = {}

    @classmethod
    def register(cls, handler: BaseStackHandler) -> None:
        cls._handlers[handler.language.lower()] = handler

    @classmethod
    def get(cls, language: str) -> Optional[BaseStackHandler]:
        lang_lower = language.lower()
        if "js" in lang_lower or "typescript" in lang_lower or "node" in lang_lower:
            lang_lower = "javascript"
        return cls._handlers.get(lang_lower)

    @classmethod
    def detect_command(cls, project_dir: str) -> Optional[str]:
        for handler in cls._handlers.values():
            cmd = handler.detect_test_command(project_dir)
            if cmd:
                return cmd
        return None


# Registrar handlers padrão
for _handler in [
    PythonStackHandler(),
    JavaStackHandler(),
    RustStackHandler(),
    GoStackHandler(),
    JSStackHandler(),
]:
    TechStackRegistry.register(_handler)
