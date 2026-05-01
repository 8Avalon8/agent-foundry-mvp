from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_foundry.builder.decision_board import apply_recommended_defaults, load_session, save_session
from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.runtime.conversation_runtime import ConversationRuntime


class CodexHandoffTest(unittest.TestCase):
    def test_codex_start_design_returns_web_url_and_a2ui_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = ConversationRuntime(Path(tmp), provider_name="mock", host="127.0.0.1", port=8765)

            started = runtime.codex_start_design(
                "我想做一个 SVN Review Agent，帮我审查 diff",
                host="127.0.0.1",
                port=8765,
            )

            self.assertEqual(started["status"], "asking")
            self.assertIn("/design/", started["web_url"])
            self.assertEqual(started["session_id"], started["a2ui_tree"]["session_id"])
            self.assertIn("web_url", started["next_codex_instruction"])

    def test_codex_continue_generates_design_card_and_agentspec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = ConversationRuntime(root, provider_name="mock", host="127.0.0.1", port=8765, run_dry_run=False)
            started = runtime.codex_start_design(
                "我想做一个 SVN Review Agent，帮我审查 diff",
                host="127.0.0.1",
                port=8765,
            )
            session_path = root / ".agent_foundry_sessions" / f"{started['session_id']}.json"
            session = load_session(session_path)
            apply_recommended_defaults(session, include_all_stages=True)
            session.metadata["confirmed_stages"] = get_stage_order(session.inferred_agent_type)
            save_session(session, session_path)

            status = runtime.codex_session(started["session_id"], host="127.0.0.1", port=8765)
            self.assertEqual(status["status"], "ready_to_build")

            completed = runtime.codex_continue(started["session_id"], host="127.0.0.1", port=8765)

            self.assertEqual(completed["status"], "completed")
            self.assertTrue(Path(completed["agent_design_card_path"]).exists())
            self.assertTrue(Path(completed["agentspec_path"]).exists())
            self.assertTrue(Path(completed["agent_dir"]).exists())
            self.assertIn("AgentSpec", completed["next_codex_instruction"])
            self.assertEqual(completed["summary"]["agent_type"], "review-agent")

    def test_codex_cli_status_continue_print_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = ConversationRuntime(root, provider_name="mock", host="127.0.0.1", port=8765, run_dry_run=False)
            started = runtime.codex_start_design(
                "我想做一个微信公众号写作 Agent，帮我把素材变成文章",
                host="127.0.0.1",
                port=8765,
            )
            self.assertEqual(started["status"], "asking")

            proc = subprocess.run(
                [sys.executable, "-m", "agent_foundry.cli", "codex-status", "missing_session", "--port", "1"],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertTrue(proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
