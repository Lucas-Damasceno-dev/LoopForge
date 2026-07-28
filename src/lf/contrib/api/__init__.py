"""API REST para o LoopForge - gerencia pipelines e runs via HTTP."""

from lf.contrib.api.app import create_app

__all__ = ["create_app"]