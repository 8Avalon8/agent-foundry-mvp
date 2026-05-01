from __future__ import annotations

import copy
import unittest

from agent_foundry.builder.decision_board import create_session
from agent_foundry.renderers.action_protocol import apply_action_event


class ActionProtocolTest(unittest.TestCase):
    def test_select_option_updates_session_and_supplemental_input(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"

        result = apply_action_event(
            session,
            {
                "action": "select_option",
                "session_id": session.id,
                "payload": {
                    "question_id": "run_tests",
                    "value": "allow_whitelist",
                    "inputs": {"test_command_whitelist": "python3 -m unittest discover -s tests -v"},
                },
            },
        )

        self.assertEqual(result.status, "accepted")
        self.assertEqual(session.get_value("run_tests"), "allow_whitelist")
        self.assertEqual(session.get_value("test_command_whitelist"), "python3 -m unittest discover -s tests -v")

    def test_invalid_option_is_rejected_without_polluting_session(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        before = copy.deepcopy(session.to_dict())

        result = apply_action_event(
            session,
            {"action": "select_option", "session_id": session.id, "payload": {"question_id": "run_tests", "value": "rm_all"}},
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(session.to_dict(), before)

    def test_missing_session_id_is_rejected_without_polluting_session(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        before = copy.deepcopy(session.to_dict())

        result = apply_action_event(
            session,
            {"action": "select_option", "payload": {"question_id": "run_tests", "value": "ask"}},
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.errors[0]["code"], "missing_session_id")
        self.assertEqual(session.to_dict(), before)

    def test_confirm_stage_requires_visible_required_decisions(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"

        result = apply_action_event(session, {"action": "confirm_stage", "session_id": session.id, "payload": {"stage": "tool_permissions"}})

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.errors[0]["code"], "missing_required_decisions")
        self.assertEqual(session.current_stage, "tool_permissions")

    def test_show_impact_and_request_approval_do_not_mutate_session(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        before = copy.deepcopy(session.to_dict())

        impact = apply_action_event(session, {"action": "show_impact", "session_id": session.id, "payload": {}})
        approval = apply_action_event(
            session,
            {
                "action": "request_approval",
                "session_id": session.id,
                "payload": {"requested_action": "wechat.publish", "reason": "发布前确认"},
            },
        )

        self.assertEqual(impact.status, "accepted")
        self.assertEqual(approval.status, "requires_approval")
        self.assertEqual(session.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
