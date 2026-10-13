"""Tool handlers. Each one returns a JSON string and does not raise."""

from __future__ import annotations

try:
    from . import client
    from .schemas import SCHEMAS
except ImportError:
    import client
    from schemas import SCHEMAS


def _handler(name: str):
    def handler(args: dict | None = None, **kwargs) -> str:
        del kwargs
        return client.call_tool(name, dict(args or {}))

    handler.__name__ = name
    return handler


HANDLERS = {name: _handler(name) for name in SCHEMAS}


def descriptions() -> dict[str, str]:
    return {name: schema["description"] for name, schema in SCHEMAS.items()}
