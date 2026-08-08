"""Gerenciador de conexões WebSocket para streaming de eventos de pipeline em tempo real.

Suporta broadcast global (conexões de /ws/streaming) e canais por run
(conexões de /ws/runs/{run_id}, que só recebem eventos do próprio run).
"""
from typing import Any

from fastapi import WebSocket


class WebSocketConnectionManager:
    """Gerencia conexões ativas WebSocket e transmite mensagens em broadcast.

    - ``active_connections``: conexões globais (feed da lista de runs, /ws/streaming).
    - ``run_connections``: mapa run_id -> conexões filtradas por run.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.run_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, run_id: str | None, websocket: WebSocket | None = None):
        """Aceita e registra a conexão.

        Aceita tanto ``connect(websocket)`` (forma legada: canal global) quanto
        ``connect(run_id, websocket)`` (canal filtrado por run).
        """
        if websocket is None:
            websocket, run_id = run_id, None  # type: ignore[assignment]
        await websocket.accept()
        self.active_connections.append(websocket)
        if run_id:
            self.run_connections.setdefault(run_id, []).append(websocket)

    def disconnect(self, run_id: str | None, websocket: WebSocket | None = None):
        """Remove a conexão dos registros global e por run.

        Aceita tanto ``disconnect(websocket)`` (forma legada) quanto
        ``disconnect(run_id, websocket)``.
        """
        if websocket is None:
            websocket, run_id = run_id, None  # type: ignore[assignment]
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if run_id:
            conns = self.run_connections.get(run_id, [])
            if websocket in conns:
                conns.remove(websocket)
                if not conns:
                    del self.run_connections[run_id]
        else:
            for rid, conns in list(self.run_connections.items()):
                if websocket in conns:
                    conns.remove(websocket)
                    if not conns:
                        del self.run_connections[rid]
                    break

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]):
        """Envia para as conexões globais (/ws/streaming), removendo as desconectadas."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_to_run(self, run_id: str, message: dict[str, Any]):
        """Envia para as conexões daquele run, removendo as desconectadas."""
        disconnected = []
        for connection in self.run_connections.get(run_id, []):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(run_id, conn)


ws_manager = WebSocketConnectionManager()
