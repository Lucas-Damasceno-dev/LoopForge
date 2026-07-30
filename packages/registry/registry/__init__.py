"""Agentic Interface Registry package."""

from .core.checker import RegistryChecker
from .core.scanner import InterfaceScanner
from .store.sqlite import RegistryStore
from .notifier.stdout import StdoutNotifier
from .notifier.slack import SlackNotifier
from .notifier.file import FileNotifier
from .store.models import InterfaceItem, BreakingChange, RegistrySchema

__version__ = "0.1.0"
__all__ = [
    "RegistryChecker",
    "InterfaceScanner",
    "RegistryStore",
    "StdoutNotifier",
    "SlackNotifier",
    "FileNotifier",
    "InterfaceItem",
    "BreakingChange",
    "RegistrySchema",
]
