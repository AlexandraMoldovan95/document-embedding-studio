"""Tests for WS /ws/containers. docker_monitor.snapshot_containers is
monkeypatched so these run with no real Docker socket needed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import monitor as monitor_module
from app.services.docker_monitor import ContainerSnapshot, DockerUnavailable


def test_websocket_streams_container_snapshot(client: TestClient, monkeypatch):
    fake = [
        ContainerSnapshot(
            id="abc123",
            name="document-embedding-studio-v2-with-chat-backend-1",
            image="document-embedding-studio-v2-with-chat-backend:latest",
            status="running",
            cpu_percent=3.2,
            memory_used_mb=512.4,
            memory_limit_mb=8192.0,
        )
    ]
    monkeypatch.setattr(monitor_module, "snapshot_containers", lambda: fake)

    with client.websocket_connect("/ws/containers") as ws:
        message = ws.receive_json()

    assert message["ok"] is True
    assert message["error"] is None
    assert len(message["containers"]) == 1
    assert message["containers"][0]["name"].endswith("backend-1")
    assert message["containers"][0]["cpu_percent"] == 3.2


def test_websocket_reports_docker_unavailable_cleanly(client: TestClient, monkeypatch):
    def raise_unavailable():
        raise DockerUnavailable("Could not reach the Docker socket.")

    monkeypatch.setattr(monitor_module, "snapshot_containers", raise_unavailable)

    with client.websocket_connect("/ws/containers") as ws:
        message = ws.receive_json()

    assert message["ok"] is False
    assert message["containers"] == []
    assert "Docker socket" in message["error"]
