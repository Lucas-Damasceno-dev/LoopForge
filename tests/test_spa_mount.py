"""Testes M-16/B4: montagem da SPA React em /app (src/lf/api/spa.py).

Sem dist (env LF_SPA_DIST inválido/ausente e pacote embutido lf.ade.static.dist
inexistente) o backend segue íntegro (GET /app → 404). Com dist, StaticFiles
html=True serve o index.html em /app/ e faz fallback SPA em deep-links.
"""

import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

INDEX_CONTENT = "<html><body><h1>LoopForge SPA</h1></body></html>"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite limpo para cada teste (padrão de test_api.py)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    db_file = ".loopforge/test_api.sqlite"
    if os.path.exists(db_file):
        with contextlib.suppress(Exception):
            os.remove(db_file)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


def _spa_dist(tmp_path, monkeypatch) -> None:
    """Cria um dist SPA mínimo e aponta LF_SPA_DIST para ele."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_CONTENT, encoding="utf-8")
    monkeypatch.setenv("LF_SPA_DIST", str(dist))


@pytest.mark.asyncio
async def test_spa_not_mounted_without_dist(tmp_path, monkeypatch):
    """(a) Sem dist válido (env inexistente) → /app responde 404, backend íntegro."""
    monkeypatch.delenv("LF_SPA_DIST", raising=False)
    monkeypatch.setenv("LF_SPA_DIST", str(tmp_path / "nao-existe"))

    app = create_app()  # não deve quebrar
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/app")
        assert resp.status_code == 404
        # o restante do backend segue respondendo
        health = await client.get("/health")
        assert health.status_code == 200


@pytest.mark.asyncio
async def test_spa_serves_index_at_root(tmp_path, monkeypatch):
    """(b) Com dist (LF_SPA_DIST) → GET /app/ serve o index.html do dist."""
    _spa_dist(tmp_path, monkeypatch)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/app/")
        assert resp.status_code == 200
        assert resp.text == INDEX_CONTENT


@pytest.mark.asyncio
async def test_spa_fallback_serves_index_html(tmp_path, monkeypatch):
    """(c) Deep-link GET /app/algum/rota cai no index.html (SPA fallback)."""
    _spa_dist(tmp_path, monkeypatch)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/app/algum/rota")
        assert resp.status_code == 200
        assert resp.text == INDEX_CONTENT
