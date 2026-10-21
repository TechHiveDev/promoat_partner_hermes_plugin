"""Unit tests for the Hermes plugin. No network."""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import client
import tools
from schemas import SCHEMAS

# Same tokens as partner-b2b-app/test/unit/_helpers/white-label-tokens.ts
_TOKENS = [
    ("minimax", re.compile(r"minimax", re.I)),
    ("h3", re.compile(r"(?<![a-z0-9_</])h3(?![a-z0-9_>])", re.I)),
    ("gemini", re.compile(r"gemini", re.I)),
    ("seedream", re.compile(r"seedream", re.I)),
    ("seedance", re.compile(r"seedance", re.I)),
    ("fabric", re.compile(r"fabric", re.I)),
    ("veed", re.compile(r"veed", re.I)),
    ("eleven", re.compile(r"eleven", re.I)),
    ("fal", re.compile(r"(?<![a-z])fal(?![a-z])", re.I)),
    ("kling", re.compile(r"kling", re.I)),
    ("sync", re.compile(r"(?<![a-z])sync(?![a-z])", re.I)),
]


def _rpc(text: str, *, error: dict | None = None, is_error: bool = False) -> str:
    if error is not None:
        body = {"jsonrpc": "2.0", "id": 1, "error": error}
    else:
        result: dict = {"content": [{"type": "text", "text": text}]}
        if is_error:
            result["isError"] = True
        body = {"jsonrpc": "2.0", "id": 1, "result": result}
    return json.dumps(body)


class _Response:
    def __init__(self, status: int, body: str, content_type: str = "application/json"):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ClientTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"PROMOAT_BASE_URL": "https://preview.example"}, clear=False)
        self._env.start()
        self._secret = patch.object(client, "_hermes_secret", return_value="pmat_testkey")
        self._secret.start()

    def tearDown(self):
        self._secret.stop()
        self._env.stop()

    def test_missing_key_does_not_ask_to_paste(self):
        with patch.object(client, "_hermes_secret", return_value=None):
            raw = client.call_tool("get_balance", {})
        body = json.loads(raw)
        self.assertEqual(body["error_code"], "UNAUTHORIZED")
        self.assertNotIn("paste your", body["message"].lower())
        self.assertIn("Do not paste the key into chat", body["message"])

    def test_key_never_read_from_os_environ(self):
        with patch.dict(os.environ, {"PROMOAT_KEY": "pmat_other_profile"}, clear=False), \
                patch.object(client, "_hermes_secret", return_value=None):
            self.assertIsNone(client.api_key())
            body = json.loads(client.call_tool("get_balance", {}))
        self.assertEqual(body["error_code"], "UNAUTHORIZED")

    def test_estimate_video_posts_with_bearer(self):
        seen = {}

        def fake_urlopen(request, timeout=300):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["auth"] = request.get_header("Authorization")
            seen["accept"] = request.get_header("Accept")
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return _Response(200, _rpc('{"credits_required": 12}'))

        with patch.object(client.urllib.request, "urlopen", fake_urlopen):
            raw = tools.HANDLERS["estimate_video"]({"mode": "talking_head", "script": "Hello"})
        self.assertEqual(json.loads(raw)["credits_required"], 12)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["url"], "https://preview.example/mcp")
        self.assertEqual(seen["auth"], "Bearer pmat_testkey")
        self.assertIn("text/event-stream", seen["accept"])
        self.assertEqual(seen["body"]["method"], "tools/call")
        self.assertEqual(seen["body"]["params"]["name"], "estimate_video")
        self.assertEqual(seen["body"]["params"]["arguments"]["mode"], "talking_head")
        self.assertNotIn("/api/partner/", seen["url"])

    def test_create_video_and_edit_send_idempotency_header(self):
        seen = []

        def fake_urlopen(request, timeout=300):
            seen.append(
                {
                    "url": request.full_url,
                    "body": json.loads(request.data.decode("utf-8")),
                }
            )
            return _Response(200, _rpc('{"workflow_id": "job-1"}'))

        with patch.object(client.urllib.request, "urlopen", fake_urlopen):
            tools.HANDLERS["create_video"](
                {"mode": "talking_head", "character_id": "11111111-1111-1111-1111-111111111111", "idempotency_key": "key-create"}
            )
            tools.HANDLERS["fix_scene"](
                {"workflowId": "job-1", "scene_index": 0, "idempotency_key": "key-edit", "dry_run": True}
            )
        create_args = seen[0]["body"]["params"]["arguments"]
        edit_args = seen[1]["body"]["params"]["arguments"]
        self.assertEqual(seen[0]["url"], "https://preview.example/mcp")
        self.assertEqual(seen[0]["body"]["params"]["name"], "create_video")
        self.assertEqual(create_args["idempotency_key"], "key-create")
        self.assertEqual(seen[1]["body"]["params"]["name"], "fix_scene")
        self.assertEqual(edit_args["workflowId"], "job-1")
        self.assertEqual(edit_args["idempotency_key"], "key-edit")
        self.assertTrue(edit_args["dry_run"])

    def test_error_body_passes_through(self):
        def fake_urlopen(request, timeout=300):
            text = '{"error_code":"QUOTE_MISMATCH","message":"price changed"}'
            return _Response(200, _rpc(text, is_error=True))

        with patch.object(client.urllib.request, "urlopen", fake_urlopen):
            raw = tools.HANDLERS["estimate_video"]({"mode": "scenes"})
        body = json.loads(raw)
        self.assertEqual(body["error_code"], "QUOTE_MISMATCH")
        self.assertEqual(body["message"], "price changed")

    def test_sse_answer_is_read(self):
        def fake_urlopen(request, timeout=300):
            payload = _rpc('{"credits_balance": 4}')
            raw = f"event: message\ndata: {payload}\n\n"
            return _Response(200, raw, "text/event-stream")

        with patch.object(client.urllib.request, "urlopen", fake_urlopen):
            raw = tools.HANDLERS["get_balance"]({})
        self.assertEqual(json.loads(raw)["credits_balance"], 4)

    def test_connection_error_returns_json(self):
        def fake_urlopen(request, timeout=300):
            raise urllib.error.URLError("timed out")

        with patch.object(client.urllib.request, "urlopen", fake_urlopen):
            raw = tools.HANDLERS["get_balance"]({})
        body = json.loads(raw)
        self.assertEqual(body["error_code"], "TRANSPORT")
        self.assertIn("timed out", body["message"])

    def test_get_job_wait_is_local_and_not_sent(self):
        seen = {}
        slept = []

        def fake_urlopen(request, timeout=300):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return _Response(200, _rpc('{"status": "running"}'))

        with patch.object(client.urllib.request, "urlopen", fake_urlopen), \
                patch.object(tools.time, "sleep", slept.append):
            raw = tools.HANDLERS["get_job"]({"workflowId": "job-1", "wait_seconds": 9})
        self.assertEqual(json.loads(raw)["status"], "running")
        self.assertEqual(slept, [9.0])
        self.assertEqual(seen["body"]["params"]["name"], "get_job")
        self.assertEqual(seen["body"]["params"]["arguments"], {"workflowId": "job-1"})

    def test_get_job_wait_is_capped_and_optional(self):
        slept = []

        def fake_urlopen(request, timeout=300):
            return _Response(200, _rpc('{"status": "running"}'))

        with patch.object(client.urllib.request, "urlopen", fake_urlopen), \
                patch.object(tools.time, "sleep", slept.append):
            tools.HANDLERS["get_job"]({"workflowId": "job-1", "wait_seconds": 999})
            tools.HANDLERS["get_job"]({"workflowId": "job-1"})
            tools.HANDLERS["get_job"]({"workflowId": "job-1", "wait_seconds": "abc"})
        self.assertEqual(slept, [float(tools.MAX_WAIT_SECONDS)])

    def test_descriptions_are_white_label(self):
        for name, description in tools.descriptions().items():
            for token, pattern in _TOKENS:
                self.assertIsNone(pattern.search(description), f"{name} leaks {token}: {description}")

    def test_manifest_lists_every_tool(self):
        text = (Path(__file__).resolve().parent / "plugin.yaml").read_text(encoding="utf-8")
        listed = re.findall(r"^  - ([a-z_]+)$", text, re.M)
        self.assertEqual(set(listed), set(SCHEMAS))
        self.assertEqual(set(listed), set(tools.HANDLERS))


if __name__ == "__main__":
    unittest.main()
