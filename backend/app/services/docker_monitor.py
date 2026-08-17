"""Read-only stats for this app's own Docker containers, for the live status
panel. Requires the Docker socket to be mounted into the backend container
(see docker-compose.yml) — this only works when running via
`docker compose up`, not when running the backend directly with uvicorn.

Security note, stated plainly: anything with access to the Docker socket can
control ANY container on the host machine, not just read stats from these
two — the socket doesn't have a "read-only" mode at the API level, regardless
of how the bind mount itself is flagged. That's an acceptable trade-off for a
local, single-user learning project, but this file only ever calls read
operations (list/stats), and the socket should never be exposed outside this
local setup (e.g. never published as a network port, never used in a
multi-tenant or internet-facing deployment).
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    import docker
    from docker.errors import DockerException
except ImportError:  # "docker" package not installed — the panel degrades cleanly
    docker = None  # type: ignore[assignment]
    DockerException = Exception  # type: ignore[assignment,misc]

LABEL_FILTER = {"label": "studio.monitor=true"}


class DockerUnavailable(Exception):
    """The Docker socket isn't reachable — most commonly because the backend
    is running via `uvicorn` directly rather than via `docker compose up`."""


@dataclass
class ContainerSnapshot:
    id: str
    name: str
    image: str
    status: str
    cpu_percent: float
    memory_used_mb: float
    memory_limit_mb: float


def _get_client():
    if docker is None:
        raise DockerUnavailable("The 'docker' Python package is not installed.")
    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as e:
        raise DockerUnavailable(
            "Could not reach the Docker socket. This panel only works when the "
            "whole app is started with `docker compose up`."
        ) from e


def _cpu_percent(stats: dict) -> float:
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        )
        online_cpus = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"]["cpu_usage"].get("percpu_usage") or [1]
        )
        if system_delta > 0 and cpu_delta >= 0:
            return round((cpu_delta / system_delta) * online_cpus * 100.0, 1)
    except (KeyError, ZeroDivisionError, TypeError):
        pass
    return 0.0


def _memory_mb(stats: dict) -> tuple[float, float]:
    try:
        usage = stats["memory_stats"].get("usage", 0)
        # Docker's raw "usage" includes reclaimable page cache; subtract it so
        # this matches what `docker stats` shows, not an inflated number.
        cache = stats["memory_stats"].get("stats", {}).get("inactive_file", 0)
        limit = stats["memory_stats"].get("limit", 0)
        used_mb = max(0, usage - cache) / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        return round(used_mb, 1), round(limit_mb, 1)
    except (KeyError, TypeError):
        return 0.0, 0.0


def snapshot_containers() -> list[ContainerSnapshot]:
    """Returns a point-in-time snapshot of every container labeled for this
    app (see the `studio.monitor` label in docker-compose.yml). Raises
    DockerUnavailable if the socket can't be reached at all."""
    client = _get_client()
    result: list[ContainerSnapshot] = []

    for container in client.containers.list(all=True, filters=LABEL_FILTER):
        stats: dict = {}
        if container.status == "running":
            try:
                stats = container.stats(stream=False)
            except DockerException:
                stats = {}

        cpu = _cpu_percent(stats) if stats else 0.0
        mem_used, mem_limit = _memory_mb(stats) if stats else (0.0, 0.0)

        image_label = container.image.tags[0] if container.image.tags else container.image.short_id

        result.append(
            ContainerSnapshot(
                id=container.short_id,
                name=container.name,
                image=image_label,
                status=container.status,
                cpu_percent=cpu,
                memory_used_mb=mem_used,
                memory_limit_mb=mem_limit,
            )
        )

    result.sort(key=lambda c: c.name)
    return result
