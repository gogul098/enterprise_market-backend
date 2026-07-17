"""
WebSocket connection manager for real-time inventory updates across all clients.
"""
from typing import List
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.main_loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            self.main_loop = asyncio.get_running_loop()
        except Exception:
            pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast JSON message to all connected clients."""
        safe_message = jsonable_encoder(message)
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(safe_message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    def broadcast_sync(self, message: dict):
        """Helper to broadcast safely from synchronous endpoints running in threadpool."""
        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.main_loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.broadcast(message))
            except Exception:
                pass

manager = ConnectionManager()
