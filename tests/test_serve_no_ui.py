"""Testes do `lf serve --no-ui`: rotas de dashboard condicionais em create_app()."""
import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app


@pytest.mark.asyncio
async def test_dashboard_route_disabled_with_no_ui():
    app = create_app(ui_enabled=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/dashboard")
        assert r.status_code == 404
        h = await ac.get("/health")
        assert h.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_route_present_by_default():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/dashboard")
        assert r.status_code == 200
