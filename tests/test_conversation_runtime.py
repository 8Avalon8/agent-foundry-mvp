from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_foundry.runtime.conversation_runtime import ConversationRuntime


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


if __name__ == "__main__":
    unittest.main()
