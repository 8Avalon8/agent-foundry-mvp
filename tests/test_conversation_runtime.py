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

from agent_foundry.runtime.conversation_runtime import ConversationRuntime
from agent_foundry.runtime.web_app import render_builder_web_app


class ConversationRuntimeTest(unittest.TestCase):
    def test_runtime_start_and_action_event_response_include_a2ui_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = ConversationRuntime(Path(tmp), provider_name="mock")

            started = runtime.start("我想做一个 SVN Review Agent，帮我审查 diff")

            self.assertEqual(started["status"], "asking")
            self.assertEqual(started["session_id"], started["a2ui_tree"]["session_id"])
            self.assertEqual(started["a2ui_tree"]["root"]["type"], "Stack")
            session_id = started["session_id"]

            responded = runtime.respond(
                {
                    "session_id": session_id,
                    "action_event": {
                        "action": "select_option",
                        "session_id": session_id,
                        "payload": {"question_id": "review_focus", "value": ["bug_risk", "test_impact"]},
                    },
                }
            )

            self.assertEqual(responded["status"], "asking")
            self.assertEqual(responded["next_question"]["id"], "lifecycle")
            self.assertEqual(responded["a2ui_tree"]["session_id"], session_id)

    def test_runtime_natural_reply_can_complete_and_generate_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = ConversationRuntime(Path(tmp), provider_name="mock")
            started = runtime.start("我想做一个微信公众号写作 Agent，帮我把素材变成文章")

            completed = runtime.respond({"session_id": started["session_id"], "natural_language_reply": "都按推荐"})

            self.assertEqual(completed["status"], "completed")
            self.assertTrue(Path(completed["agent_dir"]).exists())
            self.assertTrue((Path(completed["run_dir"]) / "permission_checks.json").exists())
            self.assertIsNotNone(completed["agent_spec_summary"])

    def test_chat_build_a2ui_json_format_outputs_renderable_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agent_foundry.cli",
                    "chat-build",
                    "我想做一个 SVN Review Agent，帮我审查 diff",
                    "--llm-provider",
                    "mock",
                    "--reply",
                    "都按推荐",
                    "--format",
                    "a2ui-json",
                    "--output",
                    tmp,
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            data = json.loads(proc.stdout)
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["session_id"], data["a2ui_tree"]["session_id"])
            self.assertEqual(data["a2ui_tree"]["root"]["type"], "Stack")
            self.assertTrue(Path(data["run_dir"]).exists())

    def test_use_recommended_action_advances_from_web_confirm_bar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = ConversationRuntime(Path(tmp), provider_name="mock")
            started = runtime.start("我想做一个 SVN Review Agent，帮我审查 diff")
            session_id = started["session_id"]

            responded = runtime.respond(
                {
                    "session_id": session_id,
                    "action_event": {
                        "action": "use_recommended",
                        "session_id": session_id,
                        "payload": {"stage": "foundation"},
                    },
                }
            )

            self.assertIn(responded["status"], {"asking", "completed"})
            self.assertEqual(responded["a2ui_tree"]["session_id"], session_id)
            self.assertTrue(responded["events"])
            self.assertEqual(responded["events"][0]["action"], "use_recommended")

    def test_web_app_html_contains_a2ui_bootstrap(self) -> None:
        html = render_builder_web_app({"provider": "mock", "output_root": "workspace/web_builder"})

        self.assertIn("Agent Foundry Builder", html)
        self.assertIn("/conversation/start", html)
        self.assertIn("renderA2UI", html)
        self.assertIn("server-config", html)

    def test_serve_web_http_smoke_generates_completed_agent(self) -> None:
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
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                _wait_for_health(base)
                html = _http_get(base + "/")
                self.assertIn("Agent Foundry Builder", html)

                started = _http_post(base + "/conversation/start", {"user_goal": "我想做一个 SVN Review Agent，帮我审查 diff"})
                completed = _http_post(
                    base + "/conversation/respond",
                    {"session_id": started["session_id"], "natural_language_reply": "都按推荐"},
                )

                self.assertEqual(completed["status"], "completed")
                self.assertTrue((Path(completed["agent_dir"]) / "agent.yaml").exists())
                self.assertTrue((Path(completed["run_dir"]) / "permission_checks.json").exists())
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
        except Exception as exc:  # pragma: no cover - failure reported below
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
