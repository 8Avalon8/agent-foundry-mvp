from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


class DesignSessionWebUrlTest(unittest.TestCase):
    def test_design_session_url_loads_existing_session(self) -> None:
        port = _free_port()
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agent_foundry.cli",
                    "serve-web",
                    "--llm-provider",
                    "mock",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--output",
                    tmp,
                    "--no-dry-run",
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                _wait_for_health(base)
                started = _http_post(base + "/codex/start-design", {"user_goal": "我想做一个 SVN Review Agent，帮我审查 diff"})

                html = _http_get(started["web_url"])
                status = _http_get(base + f"/codex/session/{started['session_id']}")

                self.assertIn("Agent Foundry Builder", html)
                self.assertIn(started["session_id"], html)
                self.assertIn("apiGet('/codex/session/'", html)
                self.assertEqual(json.loads(status)["session_id"], started["session_id"])
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _wait_for_health(base: str) -> None:
    deadline = time.time() + 8
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            health = json.loads(_http_get(base + "/health"))
            if health.get("status") in {"ok", "degraded"}:
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"server did not become healthy: {last_error}")


def _http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def _http_post(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AssertionError(exc.read().decode("utf-8")) from exc


if __name__ == "__main__":
    unittest.main()
