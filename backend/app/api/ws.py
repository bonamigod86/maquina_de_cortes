"""WebSocket: progresso em tempo real por projeto e fila global."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import bus

router = APIRouter()


@router.websocket("/api/ws/project/{project_id}")
async def project_ws(websocket: WebSocket, project_id: str):
    await websocket.accept()
    q = bus.subscribe(project_id)
    q_global = bus.subscribe("queue")
    try:
        while True:
            import asyncio

            done, _ = await asyncio.wait(
                [asyncio.ensure_future(q.get()), asyncio.ensure_future(q_global.get())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                await websocket.send_json(task.result())
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(project_id, q)
        bus.unsubscribe("queue", q_global)
