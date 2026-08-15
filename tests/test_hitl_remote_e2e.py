"""E2E HITL remoto (M-22/A9 da Fase A): decisão via POST /decide no gate, SEM stdin.

Cobre o bug vivo em que o dispatcher pollava `human_decisions` com
`run_id = thread_id` enquanto a API gravava `run_id = uuid` — a decisão nunca
casava e o gate dependia de input local. A run é criada VIA API com
interactive=True: o pipeline real da API alcança o primeiro gate (qa) e a ÚNICA
forma de avançar é o polling remoto (run_id+gate_node) consumir a decisão do
POST /decide.

B1 (A1): o decide agora VALIDA a run (404 se inexistente) e o gate_node
pendente (409 se não casar com o checkpoint) — o teste usa o run_id real e o
gate correto 'qa'. B2: a decisão é marcada como consumed ao ser aplicada.
"""

import asyncio
import sqlite3

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_hitl_env(tmp_path, monkeypatch):
    """Isola em tmp_path usando o MESMO banco da API e do dispatcher.

    IMPORTANTE: NÃO seta LF_API_TEST — sob LF_API_TEST a API escreveria em
    .loopforge/test_api.sqlite enquanto o dispatcher polla telemetry.sqlite.
    Em produção ambos usam o default sqlite+aiosqlite:///.loopforge/telemetry.sqlite.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LF_API_TEST", raising=False)
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


async def _wait_status(client: AsyncClient, run_id: str, timeout: float = 60.0) -> str:
    """Poll GET /api/v1/runs/{id} até a run sair de running."""
    waited = 0.0
    status = "queued"
    while waited < timeout:
        resp = await client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200
        status = resp.json()["status"]
        if status in ("completed", "failed", "paused"):
            return status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em {timeout}s (status: {status})")


async def _open_gate(client: AsyncClient, run_id: str, skip: set[str], timeout: float = 30.0) -> str:
    """Aguarda o evento hitl_gate_reached e devolve um gate_node AINDA NÃO
    decidido (não está em ``skip``).

    Cada gate anuncia UMA vez (dedup por run+nó no dispatcher); o helper
    ignora gates já tratados para o fluxo multi-gate (qa → parallel_audit).
    """
    waited = 0.0
    while waited < timeout:
        resp = await client.get(f"/api/v1/runs/{run_id}/events")
        assert resp.status_code == 200
        for ev in resp.json()["events"]:
            if ev.get("event") == "hitl_gate_reached":
                node = (ev.get("payload") or {}).get("gate_node")
                if node and node not in skip:
                    return node
        await asyncio.sleep(0.3)
        waited += 0.3
    raise AssertionError(f"gate não abriu em {timeout}s para a run {run_id}")


async def _decide_at_gate(
    client: AsyncClient, run_id: str, gate_node: str, payload: dict, timeout: float = 30.0
) -> None:
    """POST /decide para o gate; antes de ele abrir o contrato B1 devolve 409."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        resp = await client.post(f"/api/runs/{run_id}/decide", json={"gate_node": gate_node, **payload})
        if resp.status_code == 201:
            return
        assert resp.status_code == 409, resp.text
        if loop.time() >= deadline:
            raise AssertionError(f"decisão {gate_node} não aceita em {timeout}s: {resp.text}")
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_hitl_remote_decision_consumed_at_gate():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Run real via API com HITL: os gates (qa e parallel_audit) ficam em
        # polling remoto até a decisão do POST /decide. mock_llm=True → nós mock.
        create_resp = await client.post(
            "/api/runs",
            json={"idea": "Build HITL remote feature", "stack": "python", "mock_llm": True, "interactive": True},
        )
        assert create_resp.status_code == 201, create_resp.text
        run_id = create_resp.json()["id"]

        # Decide CADA gate que abrir (qa primeiro, parallel_audit depois).
        decided: set[str] = set()
        g1 = await _open_gate(client, run_id, decided)
        decided.add(g1)
        await _decide_at_gate(client, run_id, g1, {"action": "approve", "user": "e2e-tester"})
        g2 = await _open_gate(client, run_id, decided)
        decided.add(g2)
        await _decide_at_gate(client, run_id, g2, {"action": "approve", "user": "e2e-tester"})

        status = await _wait_status(client, run_id)
        assert status != "failed", f"run falhou: {status}"

    # Prova da chave correta: o dispatcher gravou suas próprias decisões de
    # gate com run_id = uuid (a cada gate aprovado o polling casou run_id +
    # gate_node) e as decisões da API foram CONSUMIDAS (consumed=1).
    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        total = conn.execute("SELECT COUNT(*) FROM human_decisions WHERE run_id = ?", (run_id,)).fetchone()[0]
        consumed = conn.execute(
            "SELECT COUNT(*) FROM human_decisions WHERE run_id = ? AND consumed = 1", (run_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    # 2 decisões do POST /decide (consumidas) + registros do dispatcher nos gates
    assert total >= 4, f"esperado decisões da API + registros do dispatcher, achou {total}"
    assert consumed >= 2, f"decisões remotas da API deveriam estar consumidas, achou {consumed}"
