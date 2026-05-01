from __future__ import annotations

import unittest

from agent_foundry.builder.decision_board import apply_recommended_defaults, create_session, generate_design_card


class DesignCardTest(unittest.TestCase):
    def test_design_card_groups_confirmed_and_unresolved_by_stage(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.apply_decision("review_focus", ["bug_risk"], source="user_selected")
        session.apply_decision("run_tests", "ask", source="user_selected")

        card = generate_design_card(session)
        text = card.to_markdown()

        self.assertIn("foundation", card.confirmed_by_stage)
        self.assertIn("tool_permissions", card.confirmed_by_stage)
        self.assertIn("### foundation", text)
        self.assertIn("### tool_permissions", text)
        self.assertIn("Review 重点是什么？", text)
        self.assertIn("是否允许运行测试命令？", text)

    def test_high_risk_recommended_defaults_remain_unconfirmed(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        apply_recommended_defaults(session, include_all_stages=True)

        card = generate_design_card(session)
        text = card.to_markdown()

        self.assertIn("是否允许直接修改源码？：尚未确认", text)
        self.assertIn("风险：high", text)
        confirmed_tool_items = card.confirmed_by_stage.get("tool_permissions", [])
        self.assertFalse(any("是否允许直接修改源码？" in item for item in confirmed_tool_items))

    def test_user_selected_high_risk_decision_is_confirmed(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.apply_decision("source_modify_policy", "ask", source="user_selected")

        card = generate_design_card(session)

        confirmed_tool_items = card.confirmed_by_stage.get("tool_permissions", [])
        self.assertTrue(any("是否允许直接修改源码？：ask" in item for item in confirmed_tool_items))


if __name__ == "__main__":
    unittest.main()
