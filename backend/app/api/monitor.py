"""WS /ws/containers — pushes a live snapshot of this app's own Docker
containers every couple of seconds. Strictly observational: no start/stop/
restart controls here, on purpose (see the security note in
app/services/docker_monitor.py for why this stays read-only).
"""
from __future__ import annotations

import asyncio
import dataclasses

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.services.docker_monitor import DockerUnavailable, snapshot_containers

router = APIRouter(tags=["monitor"])

_POLL_INTERVAL_SECONDS = 2.0


@router.websocket("/ws/containers")
async def containers_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                containers = await run_in_threadpool(snapshot_containers)
                payload = {
                    "ok": True,
                    "containers": [dataclasses.asdict(c) for c in containers],
                    "error": None,
                }
            except DockerUnavailable as e:
                payload = {"ok": False, "containers": [], "error": str(e)}

            await websocket.send_json(payload)
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
