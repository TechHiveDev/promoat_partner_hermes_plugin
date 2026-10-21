"""Tool handlers. Each one returns a JSON string and does not raise."""

from __future__ import annotations

import time

try:
    from . import client
    from .schemas import SCHEMAS
except ImportError:
    import client
    from schemas import SCHEMAS

# Longest pause get_job may add before polling. Kept well under typical tool timeouts.
MAX_WAIT_SECONDS = 30


def _handler(name: str):
    def handler(args: dict | None = None, **kwargs) -> str:
        del kwargs
        return client.call_tool(name, dict(args or {}))

    handler.__name__ = name
    return handler


def _get_job_handler(args: dict | None = None, **kwargs) -> str:
    """get_job with a plugin-side pause.

    `wait_seconds` never reaches the server: it is removed here, the plugin sleeps,
    then the normal get_job call is made. This lets the agent poll every 8-10 s
    without running a sleep script (which needs a manual approval click).
    """
    del kwargs
    payload = dict(args or {})
    raw_wait = payload.pop("wait_seconds", None)
    try:
        wait = float(raw_wait) if raw_wait is not None else 0.0
    except (TypeError, ValueError):
        wait = 0.0
    wait = max(0.0, min(wait, float(MAX_WAIT_SECONDS)))
    if wait:
        time.sleep(wait)
    return client.call_tool("get_job", payload)


_get_job_handler.__name__ = "get_job"

HANDLERS = {name: _handler(name) for name in SCHEMAS}
HANDLERS["get_job"] = _get_job_handler


def descriptions() -> dict[str, str]:
    return {name: schema["description"] for name, schema in SCHEMAS.items()}
