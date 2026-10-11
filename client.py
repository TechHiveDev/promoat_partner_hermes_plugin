"""HTTP client for the Promoat Partner API. Handlers always get a JSON string."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://platform.promoat.ai"
_KEY_RE = re.compile(r"pmat_[A-Za-z0-9_]+")


def base_url() -> str:
    raw = os.environ.get("PROMOAT_BASE_URL", "").strip() or DEFAULT_BASE
    return raw.rstrip("/")


def api_key() -> str | None:
    secret = _hermes_secret("PROMOAT_KEY")
    if secret:
        return secret
    env = os.environ.get("PROMOAT_KEY", "").strip()
    return env or None


def _hermes_secret(name: str) -> str | None:
    try:
        from agent.secret_scope import get_secret
    except Exception:
        return None
    try:
        value = get_secret(name)
    except Exception:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def call(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    query: dict | None = None,
    idempotency_key: str | None = None,
) -> str:
    key = api_key()
    if not key:
        return _dumps(
            {
                "error_code": "UNAUTHORIZED",
                "message": (
                    "PROMOAT_KEY is not set. Add it in Hermes when the plugin asks, "
                    "or export PROMOAT_KEY in the shell. Do not paste the key into chat."
                ),
            }
        )

    url = base_url() + path
    filtered = {k: v for k, v in (query or {}).items() if v is not None}
    if filtered:
        url += "?" + urllib.parse.urlencode({k: _query_value(v) for k, v in filtered.items()})

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if body is not None and method not in ("GET", "DELETE"):
        payload = {k: v for k, v in body.items() if v is not None}
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8")
            return _as_json(raw, getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return _as_json(raw, exc.code)
    except Exception as exc:
        return _dumps({"error_code": "TRANSPORT", "message": _redact(str(exc))})


def _query_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _as_json(raw: str, status: int) -> str:
    text = (raw or "").strip()
    if not text:
        return _dumps({"error_code": f"HTTP_{status}", "message": f"Empty response ({status})"})
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _dumps({"error_code": f"HTTP_{status}", "message": _redact(text[:2000])})
    if isinstance(parsed, (dict, list)):
        return _dumps(parsed)
    return _dumps({"result": parsed})


def _dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _redact(text: str) -> str:
    return _KEY_RE.sub("pmat_…", text)
