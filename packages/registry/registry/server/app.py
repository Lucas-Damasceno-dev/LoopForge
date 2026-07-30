"""Servidor HTTP REST (FastAPI) para registry serve."""

from typing import Optional
from fastapi import FastAPI, HTTPException
from registry.core.checker import RegistryChecker
from registry.core.scanner import InterfaceScanner
from registry.store.sqlite import RegistryStore


def create_registry_app(repo_root: str = ".") -> FastAPI:
    app = FastAPI(title="Agentic Interface Registry API", version="1.0.0")

    @app.get("/interfaces")
    def get_interfaces():
        store = RegistryStore(repo_root)
        schema = store.load()
        if not schema:
            scanner = InterfaceScanner(repo_root)
            schema = scanner.scan()
            store.save(schema)
        return schema.model_dump()

    @app.get("/check")
    def check_breaking(agent: Optional[str] = None):
        checker = RegistryChecker(repo_root)
        breaking = checker.check(agent=agent)
        return {"breaking_changes": [b.model_dump() for b in breaking]}

    @app.get("/uncovered")
    def get_uncovered():
        checker = RegistryChecker(repo_root)
        uncovered = checker.uncovered_interfaces()
        return {"uncovered_count": len(uncovered), "interfaces": [i.model_dump() for i in uncovered]}

    return app
