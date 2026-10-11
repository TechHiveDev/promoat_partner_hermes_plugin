"""Tool handlers. Each one returns a JSON string and does not raise."""

from __future__ import annotations

import json
from urllib.parse import quote

try:
    from . import client
    from .schemas import SCHEMAS
except ImportError:
    import client
    from schemas import SCHEMAS

# method, path template, path params, query keys, whether idempotency_key is a header.
_ROUTES: dict[str, dict] = {
    "estimate_video": {"method": "POST", "path": "/api/partner/v1/videos/estimate"},
    "create_video": {"method": "POST", "path": "/api/partner/v1/videos", "idempotency": True},
    "create_character": {"method": "POST", "path": "/api/partner/v1/characters"},
    "clone_voice": {"method": "POST", "path": "/api/partner/v1/voices"},
    "list_voices": {"method": "GET", "path": "/api/partner/v1/voices"},
    "get_balance": {"method": "GET", "path": "/api/partner/v1/usage/summary", "query": ("from", "to")},
    "get_job": {"method": "GET", "path": "/api/partner/v1/jobs/{workflowId}/status", "path_params": ("workflowId",)},
    "get_scenes": {"method": "GET", "path": "/api/partner/v1/videos/{workflowId}/scenes", "path_params": ("workflowId",)},
    "fix_scene": {
        "method": "POST",
        "path": "/api/partner/v1/videos/{workflowId}/fix-scene",
        "path_params": ("workflowId",),
        "idempotency": True,
    },
    "edit_script": {
        "method": "POST",
        "path": "/api/partner/v1/videos/{workflowId}/edit-script",
        "path_params": ("workflowId",),
        "idempotency": True,
    },
    "fix_sound": {
        "method": "POST",
        "path": "/api/partner/v1/videos/{workflowId}/fix-sound",
        "path_params": ("workflowId",),
        "idempotency": True,
    },
    "list_characters": {"method": "GET", "path": "/api/partner/v1/characters"},
    "get_character": {"method": "GET", "path": "/api/partner/v1/characters/{id}", "path_params": ("id",)},
    "delete_character": {"method": "DELETE", "path": "/api/partner/v1/characters/{id}", "path_params": ("id",)},
    "regenerate_character": {
        "method": "POST",
        "path": "/api/partner/v1/characters/{id}/regenerate",
        "path_params": ("id",),
    },
    "list_voice_presets": {"method": "GET", "path": "/api/partner/v1/voices/presets"},
    "delete_voice": {"method": "DELETE", "path": "/api/partner/v1/voices/{id}", "path_params": ("id",)},
    "reclone_voice": {"method": "POST", "path": "/api/partner/v1/voices/{id}/reclone", "path_params": ("id",)},
    "synthesize_speech": {"method": "POST", "path": "/api/partner/v1/tts"},
    "create_first_frame": {"method": "POST", "path": "/api/partner/v1/images/first-frame"},
    "plan_scenes": {"method": "POST", "path": "/api/partner/v1/videos/scene-plan"},
    "list_assets": {"method": "GET", "path": "/api/partner/v1/assets", "query": ("kind", "limit", "offset")},
    "get_asset": {"method": "GET", "path": "/api/partner/v1/assets/{id}", "path_params": ("id",)},
    "list_jobs": {"method": "GET", "path": "/api/partner/v1/usage/jobs", "query": ("limit", "offset")},
}


def _handler(name: str):
    spec = _ROUTES[name]

    def handler(args: dict | None = None, **kwargs) -> str:
        del kwargs
        payload = dict(args or {})
        idempotency_key = payload.pop("idempotency_key", None) if spec.get("idempotency") else None
        path = spec["path"]
        for param in spec.get("path_params", ()):
            value = payload.pop(param, None)
            if value is None or value == "":
                return json.dumps({"error_code": "INVALID_INPUT", "message": f"Missing {param}"})
            path = path.replace("{" + param + "}", quote(str(value), safe=""))
        query = None
        if spec.get("query"):
            query = {key: payload.pop(key, None) for key in spec["query"]}
        body = None if spec["method"] in ("GET", "DELETE") else payload
        return client.call(
            spec["method"],
            path,
            body=body,
            query=query,
            idempotency_key=idempotency_key or None,
        )

    handler.__name__ = name
    return handler


HANDLERS = {name: _handler(name) for name in _ROUTES}


def descriptions() -> dict[str, str]:
    return {name: schema["description"] for name, schema in SCHEMAS.items()}
