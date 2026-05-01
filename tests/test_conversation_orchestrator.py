from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_foundry.builder.conversation_orchestrator import handle_action_event, handle_user_reply, start_conversation
from agent_foundry.llm.mock_provider import MockLLMProvider


class ConversationOrchestratorTest(unittest.TestCase):
    def test_conversation_asks_next_question_from_natural_goal(self) -> None:
        result = start_conversation("我想做一个 SVN Review Agent，帮我审查 diff")

        self.assertEqual(result.status, "asking")
        self.assertIsNotNone(result.next_question)
        self.assertEqual(result.next_question.id, "review_focus")

    def test_natural_reply_becomes_action_event_and_advances_question(self) -> None:
        result = start_conversation("我想做一个 SVN Review Agent，帮我审查 diff")
        session = result.session

        result = handle_user_reply(session, "重点看 bug_risk 和 test_impact")

        self.assertEqual(result.status, "asking")
        self.assertEqual(session.get_value("review_focus"), ["bug_risk", "test_impact"])
        self.assertEqual(result.events[0]["status"], "accepted")
        self.assertEqual(result.next_question.id, "lifecycle")

    def test_completed_stage_waits_for_explicit_confirmation(self) -> None:
        result = start_conversation("我想做一个 SVN Review Agent，帮我审查 diff")
        session = result.session

        result = handle_user_reply(session, "重点看 bug_risk 和 test_impact")
        self.assertEqual(result.next_question.id, "lifecycle")

        result = handle_user_reply(session, "按需运行")

        self.assertEqual(result.status, "awaiting_confirmation")
        self.assertEqual(session.current_stage, "foundation")
        self.assertIsNone(result.next_question)

        result = handle_action_event(
            session,
            {"action": "confirm_stage", "session_id": session.id, "payload": {"stage": "foundation"}},
        )

        self.assertEqual(result.status, "asking")
        self.assertEqual(session.current_stage, "autonomy")
        self.assertEqual(result.next_question.id, "autonomy_level")

    def test_natural_preference_patch_does_not_pollute_current_question(self) -> None:
        provider = MockLLMProvider()
        result = start_conversation("我想做一个 SVN Review Agent，帮我审查 diff", provider=provider)
        session = result.session

        result = handle_user_reply(session, "可以读项目上下文，但不能自动写文件", provider=provider)

        self.assertEqual(result.status, "asking")
        self.assertNotIn("review_focus", session.decisions)
        self.assertEqual(session.get_value("context_scope"), "project_search")
        self.assertEqual(session.get_value("source_modify_policy"), "deny")
        self.assertEqual(result.next_question.id, "review_focus")

    def test_accept_recommended_compiles_and_dry_runs(self) -> None:
        provider = MockLLMProvider()
        result = start_conversation("我想做一个微信公众号写作 Agent，帮我把素材变成文章", provider=provider)

        with tempfile.TemporaryDirectory() as tmp:
            result = handle_user_reply(result.session, "都按推荐", provider=provider, output_root=Path(tmp), run_dry_run=True)

            self.assertEqual(result.status, "completed")
            self.assertTrue((result.agent_dir / "agent.yaml").exists())
            self.assertTrue((result.run_dir / "permission_checks.json").exists())
            checks = json.loads((result.run_dir / "permission_checks.json").read_text(encoding="utf-8"))["checks"]
            self.assertFalse([entry for entry in checks if entry["status"] == "allowed" and entry["risk"] in {"high", "critical"}])


if __name__ == "__main__":
    unittest.main()
