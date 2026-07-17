"""
WebSocket endpoint for real-time multi-device inventory synchronization.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.ws_manager import manager

router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/inventory")
async def websocket_inventory(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open and respond to heartbeats/pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
