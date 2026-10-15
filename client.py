"""MCP client for the Promoat Partner API. Handlers always get a JSON string."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_BASE = "https://promoat-platform-plugins.vercel.app"
_KEY_RE = re.compile(r"pmat_[A-Za-z0-9_]+")


def base_url() -> str:
    raw = os.environ.get("PROMOAT_BASE_URL", "").strip() or DEFAULT_BASE
    return raw.rstrip("/")


def mcp_url() -> str:
    base = base_url()
    if base.endswith("/mcp"):
        return base
    return base + "/mcp"


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


def call_tool(name: str, args: dict | None = None) -> str:
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

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args or {}},
    }
    request = urllib.request.Request(
        mcp_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            return _from_rpc(raw, content_type, getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return _dumps(
                {
                    "error_code": "UNAUTHORIZED",
                    "message": (
                        "Promoat rejected the API key. Check PROMOAT_KEY in Hermes. "
                        "Do not paste the key into chat."
                    ),
                }
            )
        raw = exc.read().decode("utf-8", errors="replace")
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        return _from_rpc(raw, content_type, exc.code)
    except Exception as exc:
        return _dumps({"error_code": "TRANSPORT", "message": _redact(str(exc))})


def _from_rpc(raw: str, content_type: str, status: int) -> str:
    text = _sse_payload(raw) if "text/event-stream" in content_type else (raw or "").strip()
    if not text:
        return _dumps({"error_code": f"HTTP_{status}", "message": f"Empty response ({status})"})
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _dumps({"error_code": f"HTTP_{status}", "message": _redact(text[:2000])})
    if not isinstance(parsed, dict):
        return _dumps({"result": parsed})
    if parsed.get("error"):
        err = parsed["error"]
        message = err.get("message") if isinstance(err, dict) else str(err)
        return _dumps(
            {
                "error_code": "CLIENT_ERROR",
                "message": _redact(message or "Promoat could not run this tool."),
            }
        )
    result = parsed.get("result")
    if not isinstance(result, dict):
        return _dumps({"error_code": f"HTTP_{status}", "message": "Promoat returned no result."})
    parts = [
        part["text"]
        for part in result.get("content") or []
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    ]
    joined = "\n".join(parts)
    if not joined:
        return _dumps({"error_code": f"HTTP_{status}", "message": "Promoat returned no result."})
    return joined


def _sse_payload(raw: str) -> str:
    data = [line[5:].strip() for line in (raw or "").splitlines() if line.startswith("data:")]
    data = [item for item in data if item]
    return data[-1] if data else ""


def _dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _redact(text: str) -> str:
    return _KEY_RE.sub("pmat_…", text)
