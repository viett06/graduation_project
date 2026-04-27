from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import logging
import asyncio

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept websocket connection and store client
        """
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove client safely
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_rate_update(self, bank_code: str, changes: dict):
        """
        Called from crawler_service._notify_update()

        Send realtime rate update event to all connected clients
        """
        if not self.active_connections:
            return

        message = {
            "event": "RATE_UPDATED",
            "bank_code": bank_code.upper(),
            "changes": changes,
            "timestamp": datetime.utcnow().isoformat()
        }

        dead_connections = []

        for conn in self.active_connections:
            try:
                await conn.send_json(message)

            except WebSocketDisconnect:
                dead_connections.append(conn)

            except Exception as e:
                logger.warning(f"WebSocket send failed: {e}")
                dead_connections.append(conn)

        for conn in dead_connections:
            self.disconnect(conn)


manager = WebSocketManager()