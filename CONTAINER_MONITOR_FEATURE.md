# What's new: Container status panel (live, via WebSocket)

A small panel on the main page showing this app's own two Docker containers
(backend, frontend) — status, CPU %, memory used/limit — updating live every
2 seconds over a WebSocket. Read-only: it observes, it does not
start/stop/restart anything.

## Important — this only works via Docker

This panel needs the Docker socket, which is only mounted into the backend
when you run the whole app with:

```
docker compose up
```

If you're running the backend the old way (`uvicorn app.main:app --reload`),
the panel will show a message saying Docker isn't reachable — that's
expected, not a bug. The manual venv/npm workflow still works exactly as
before for everything else (ingest, search, chat); only this one panel needs
the Docker path specifically.

## Security note — read this before reusing this pattern elsewhere

Giving a container access to `/var/run/docker.sock` (the Docker socket)
effectively gives it root-level control over your whole machine's Docker
setup — not just "read stats from these two containers." The `:ro`
(read-only) flag on the bind mount only makes the socket *file* unwritable
from inside the container; it does **not** restrict which Docker API calls
can be made over that socket. Anything with access to it could, in
principle, start, stop, or inspect any container on the host, not just this
app's own two.

This is a common, generally-accepted trade-off for small, local,
single-user tools (Portainer and similar dashboards work the same way) — but
it is not something to casually copy into a multi-user or internet-facing
setup. This project's own code only ever calls read operations (`list`,
`stats`) — never anything that starts, stops, or modifies a container — and
the socket is never published as a network port or exposed outside your own
machine.

## How it works

- **Labels, not names** — `docker-compose.yml` now tags both services with
  `studio.monitor: "true"`. The backend queries containers by that label
  (`docker_monitor.py`), so this keeps working regardless of what folder
  name or Docker Compose project name you're using — no hardcoded container
  names anywhere.
- **Backend**: `GET`-style polling isn't used here on purpose — the backend
  opens a WebSocket (`WS /ws/containers`), and every 2 seconds pushes a
  fresh snapshot (CPU %, memory, status) for every labeled container, computed
  from Docker's raw stats API the same way `docker stats` does.
- **Frontend**: `ContainerMonitor.tsx` opens the WebSocket on mount, renders
  a card per container, and auto-reconnects every 3 seconds if the
  connection drops (e.g. if you restart the backend container while the
  page is open).

## What changed under the hood

**Backend**
- `app/services/docker_monitor.py` — new. Talks to the Docker socket via the
  `docker` Python package, computes CPU % and memory the same way the
  `docker stats` CLI command does, returns clean dataclasses.
- `app/api/monitor.py` — new. `WS /ws/containers`, pushes a snapshot every 2
  seconds until the client disconnects.
- `pyproject.toml` — added `docker>=7.0`.
- `tests/test_monitor.py` — new, 2 tests. `snapshot_containers` is
  monkeypatched, so these run with no real Docker socket needed — same
  approach as the LLM provider tests. All 71 tests (69 + 2 new) pass.
- `docker-compose.yml` — added the `studio.monitor` / `studio.role` labels
  to both services, and the read-only Docker socket bind mount on the
  backend only (the frontend doesn't need it).

**Frontend**
- `components/ContainerMonitor.tsx` — new. WebSocket client, connection
  status indicator, per-container cards with a memory usage bar.
- `lib/types.ts` — added `ContainerSnapshot`, `ContainerMonitorMessage`.
- `lib/api.ts` — added `WS_URL`, derived from the existing `API_URL` by
  swapping the scheme (`http` → `ws`), so no new environment variable is
  needed.
- `app/page.tsx` — added the new panel after the chat section.

## Verified before delivery

`pip install -e ".[dev]"`, `pytest` (71/71 pass), `npm install`,
`npx tsc --noEmit` (clean), `npm run build` (production build succeeds).
Not testable in this sandbox: a real Docker socket connection (this
environment has no Docker daemon) — that part you'll confirm by running
`docker compose up --build` on your machine, since the code change requires
rebuilding the images (new dependency, new compose config).

## Known limitations

- Only shows this app's own two containers, by design (you chose this
  scope) — not a general-purpose Docker dashboard.
- No historical graph, just the current live value each tick.
- If the backend container itself is unhealthy or slow, the panel's own
  data will lag along with it, since the snapshot is computed inside that
  same container.
