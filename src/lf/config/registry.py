"""Registry pattern para TechStackHandlers.
Desacopla a resolução de linguagens, ferramentas de teste e gerenciadores de pacote do core.
"""

import configparser
import os
from abc import ABC, abstractmethod

ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "javascript",
    "typescript": "javascript",
    "node": "javascript",
    "express": "javascript",
    "py": "python",
    "rs": "rust",
    "golang": "go",
}


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
    def detect_test_command(self, project_dir: str) -> str | None:
        pass

    def get_fallback_test_command(self) -> str:
        return self.default_test_harness


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

    def _has_pytest_config(self, project_dir: str) -> bool:
        pyproject_path = os.path.join(project_dir, "pyproject.toml")
        if os.path.exists(pyproject_path):
            with open(pyproject_path, encoding="utf-8") as pyproject_file:
                pyproject_content = pyproject_file.read()
            if "[tool.pytest.ini_options]" in pyproject_content:
                return True

        for ini_file in ("setup.cfg", "pytest.ini", "tox.ini"):
            ini_path = os.path.join(project_dir, ini_file)
            if not os.path.exists(ini_path):
                continue
            parser = configparser.ConfigParser()
            parser.read(ini_path, encoding="utf-8")
            if parser.has_section("pytest"):
                return True
            if ini_file == "setup.cfg" and parser.has_section("tool:pytest"):
                return True

        return False

    def _has_test_files(self, project_dir: str) -> bool:
        tests_dir = os.path.join(project_dir, "tests")
        if not os.path.isdir(tests_dir):
            return False
        for root, _, files in os.walk(tests_dir):
            for file_name in files:
                if file_name.endswith(".py") and (
                    file_name.startswith("test_") or file_name.endswith("_test.py")
                ):
                    return True
        return False

    def detect_test_command(self, project_dir: str) -> str | None:
        if (
            self._has_test_files(project_dir)
            or os.path.exists(os.path.join(project_dir, "conftest.py"))
            or self._has_pytest_config(project_dir)
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

    def detect_test_command(self, project_dir: str) -> str | None:
        if os.path.exists(os.path.join(project_dir, "pom.xml")):
            return "mvn test"
        if os.path.exists(os.path.join(project_dir, "build.gradle")):
            return "./gradlew test"
        return None

    def get_fallback_test_command(self) -> str:
        return "mvn test"


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

    def detect_test_command(self, project_dir: str) -> str | None:
        if os.path.exists(os.path.join(project_dir, "Cargo.toml")):
            return "cargo test"
        return None

    def get_fallback_test_command(self) -> str:
        return "cargo test"


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

    def detect_test_command(self, project_dir: str) -> str | None:
        if os.path.exists(os.path.join(project_dir, "go.mod")):
            return "go test ./..."
        return None

    def get_fallback_test_command(self) -> str:
        return "go test ./..."


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

    def detect_test_command(self, project_dir: str) -> str | None:
        pkg_path = os.path.join(project_dir, "package.json")
        if os.path.exists(pkg_path):
            if os.path.exists(os.path.join(project_dir, "vitest.config.ts")) or os.path.exists(os.path.join(project_dir, "vitest.config.js")):
                return "npx vitest run"
            return "npm test"
        return None

    def get_fallback_test_command(self) -> str:
        return "npm test"


class TechStackRegistry:
    """Registro global extensível para manipuladores de linguagem/stack."""
    _handlers: dict[str, BaseStackHandler] = {}

    @classmethod
    def register(cls, handler: BaseStackHandler) -> None:
        cls._handlers[handler.language.lower()] = handler

    @classmethod
    def get(cls, language: str) -> BaseStackHandler | None:
        if not language:
            return None
        lang_lower = language.lower().strip()
        lang_resolved = ALIASES.get(lang_lower, lang_lower)
        return cls._handlers.get(lang_resolved)

    @classmethod
    def detect_command(cls, project_dir: str) -> str | None:
        for handler in cls._handlers.values():
            cmd = handler.detect_test_command(project_dir)
            if cmd:
                return cmd
        return None


for _handler in [
    PythonStackHandler(),
    JavaStackHandler(),
    RustStackHandler(),
    GoStackHandler(),
    JSStackHandler(),
]:
    TechStackRegistry.register(_handler)
