"""Testes unitários do WebSocketConnectionManager (lf.api.websocket_manager).

Cobre os branches que os testes de integração (test_ws_run_filter.py,
test_api_coverage.py) não alcançam:

- Forma legada de ``connect``/``disconnect`` (primeiro arg = WebSocket).
- ``send_to_run``: isolamento entre canais de run e cleanup de conexão com falha.
- ``broadcast``: remoção de conexões que falham ao enviar.
- ``disconnect``: deleção da chave do run quando a lista esvazia.

Não toca banco/app: usa um FakeWebSocket, então roda sem DB e sem race com
a suíte concorrente.
"""

from __future__ import annotations

import pytest

from lf.api.websocket_manager import WebSocketConnectionManager


class FakeWebSocket:
    """WebSocket falso com contadores observáveis; falha em send quando pedido."""

    def __init__(self, fail_send: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self.fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail_send:
            raise RuntimeError("falha simulada de envio")
        self.sent.append(message)


# ─── connect ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_forma_legada_registra_global():
    """connect(websocket) (legado) aceita e registra apenas no canal global."""
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()

    await manager.connect(ws)  # type: ignore[arg-type]

    assert ws.accepted
    assert manager.active_connections == [ws]
    assert manager.run_connections == {}


@pytest.mark.asyncio
async def test_connect_sem_websocket_e_sem_run_id_asserta():
    """connect(None) sem websocket dispara AssertionError (contracto legado)."""
    manager = WebSocketConnectionManager()

    with pytest.raises(AssertionError):
        await manager.connect(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_connect_com_run_id_registra_canal_filtrado():
    """connect(run_id, ws) registra no global E no canal da run."""
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()

    await manager.connect("run-1", ws)  # type: ignore[arg-type]

    assert ws.accepted
    assert ws in manager.active_connections
    assert manager.run_connections == {"run-1": [ws]}


@pytest.mark.asyncio
async def test_connect_mesmo_run_acumula_duas_conexoes():
    manager = WebSocketConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()

    await manager.connect("run-1", ws1)  # type: ignore[arg-type]
    await manager.connect("run-1", ws2)  # type: ignore[arg-type]

    assert manager.run_connections["run-1"] == [ws1, ws2]


# ─── disconnect ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_disconnect_forma_legada_limpa_global_e_canais():
    """disconnect(websocket) remove do global e de qualquer canal de run."""
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("run-1", ws)  # type: ignore[arg-type]

    manager.disconnect(ws)  # type: ignore[arg-type]

    assert ws not in manager.active_connections
    assert manager.run_connections == {}


@pytest.mark.asyncio
async def test_disconnect_legado_remove_apenas_um_de_varios():
    """disconnect(ws) com vários no canal remove só aquele (break do loop)."""
    manager = WebSocketConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect("run-1", ws1)  # type: ignore[arg-type]
    await manager.connect("run-1", ws2)  # type: ignore[arg-type]

    manager.disconnect(ws1)  # type: ignore[arg-type]

    assert manager.run_connections == {"run-1": [ws2]}


@pytest.mark.asyncio
async def test_disconnect_com_run_id_deleta_chave_quando_vazia():
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("run-1", ws)  # type: ignore[arg-type]

    manager.disconnect("run-1", ws)  # type: ignore[arg-type]

    assert ws not in manager.active_connections
    assert "run-1" not in manager.run_connections


@pytest.mark.asyncio
async def test_disconnect_com_run_id_sem_conexao_e_noop():
    """disconnect de run_id sem conexões não quebra nem remove a ws."""
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("run-1", ws)  # type: ignore[arg-type]

    manager.disconnect("run-2", ws)  # type: ignore[arg-type]

    assert ws in manager.active_connections
    assert manager.run_connections == {"run-1": [ws]}


@pytest.mark.asyncio
async def test_disconnect_de_conexao_nao_registrada_e_noop():
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()
    await manager.connect("run-1", ws)  # type: ignore[arg-type]
    estranho = FakeWebSocket()

    manager.disconnect("run-1", estranho)  # type: ignore[arg-type]

    assert manager.active_connections == [ws]


# ─── send_personal_message ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_personal_message_envia_json():
    manager = WebSocketConnectionManager()
    ws = FakeWebSocket()

    await manager.send_personal_message({"event": "connected"}, ws)  # type: ignore[arg-type]

    assert ws.sent == [{"event": "connected"}]


# ─── broadcast ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_entrega_para_todas_as_globais():
    manager = WebSocketConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws1)  # type: ignore[arg-type]
    await manager.connect(ws2)  # type: ignore[arg-type]

    await manager.broadcast({"event": "run_created"})

    assert ws1.sent == [{"event": "run_created"}]
    assert ws2.sent == [{"event": "run_created"}]


@pytest.mark.asyncio
async def test_broadcast_remove_conexao_que_falha_ao_enviar():
    """Conexão com send_json quebrado é removida; as demais continuam ok."""
    manager = WebSocketConnectionManager()
    ok = FakeWebSocket()
    bad = FakeWebSocket(fail_send=True)
    await manager.connect(ok)  # type: ignore[arg-type]
    await manager.connect(bad)  # type: ignore[arg-type]

    await manager.broadcast({"event": "x"})

    assert ok.sent == [{"event": "x"}]
    assert bad not in manager.active_connections


# ─── send_to_run ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_to_run_so_entrega_para_canal_da_run():
    """Isolamento: broadcast por run não vaza para o canal global nem outra run."""
    manager = WebSocketConnectionManager()
    global_ws = FakeWebSocket()
    run_ws = FakeWebSocket()
    outra_run_ws = FakeWebSocket()
    await manager.connect(global_ws)  # type: ignore[arg-type]
    await manager.connect("run-1", run_ws)  # type: ignore[arg-type]
    await manager.connect("run-2", outra_run_ws)  # type: ignore[arg-type]

    await manager.send_to_run("run-1", {"event": "node_execution"})

    assert run_ws.sent == [{"event": "node_execution"}]
    assert global_ws.sent == []
    assert outra_run_ws.sent == []


@pytest.mark.asyncio
async def test_send_to_run_run_inexistente_e_noop():
    manager = WebSocketConnectionManager()

    await manager.send_to_run("nao-existe", {"event": "x"})  # não levanta


@pytest.mark.asyncio
async def test_send_to_run_remove_conexao_que_falha_e_deleta_chave():
    manager = WebSocketConnectionManager()
    bad = FakeWebSocket(fail_send=True)
    await manager.connect("run-1", bad)  # type: ignore[arg-type]

    await manager.send_to_run("run-1", {"event": "x"})

    assert "run-1" not in manager.run_connections
    assert bad not in manager.active_connections
