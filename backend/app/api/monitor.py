"""WS /ws/containers — pushes a live snapshot of this app's own Docker
containers every couple of seconds. Strictly observational: no start/stop/
restart controls here, on purpose (see the security note in
app/services/docker_monitor.py for why this stays read-only).
"""
from __future__ import annotations

import asyncio
import dataclasses

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import SettingsDep
from app.services.docker_monitor import DockerUnavailable, snapshot_containers

router = APIRouter(tags=["monitor"])

_POLL_INTERVAL_SECONDS = 2.0


@router.websocket("/ws/containers")
async def containers_ws(websocket: WebSocket, settings: SettingsDep) -> None:
    # CORS does not apply to WebSockets: a browser opens the connection for any
    # page and only reports where the page came from in the Origin header.
    # Without this check, any website open in the same browser could read the
    # container list. Browsers always send Origin; a request without it comes
    # from a script, not a web page, and the compose file only publishes the
    # port on 127.0.0.1, so such a script has to run on this machine.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.cors_origin_list:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
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
