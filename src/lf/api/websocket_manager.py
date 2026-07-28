"""Gerenciador de conexões WebSocket para streaming de eventos de pipeline em tempo real."""
from typing import Any

from fastapi import WebSocket


class WebSocketConnectionManager:
    """Gerencia conexões ativas WebSocket e transmite mensagens em broadcast."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = WebSocketConnectionManager()
