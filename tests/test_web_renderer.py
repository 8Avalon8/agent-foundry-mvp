from __future__ import annotations

import unittest

from agent_foundry.builder.decision_board import build_decision_board, create_session
from agent_foundry.renderers.web_renderer import board_to_web_view_model, render_web_html


class WebRendererTest(unittest.TestCase):
    def test_web_view_model_contains_expected_components_without_mutating_board(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        board = build_decision_board(session)
        before = board.to_dict()

        model = board_to_web_view_model(board)

        self.assertEqual(board.to_dict(), before)
        component_types = [component["type"] for component in model["components"]]
        self.assertIn("AgentSummaryCard", component_types)
        self.assertIn("PresetCardGroup", component_types)
        self.assertIn("DecisionCard", component_types)
        self.assertIn("ImpactPreview", component_types)
        self.assertIn("StageProgress", component_types)
        self.assertIn("ConfirmBar", component_types)

    def test_web_html_embeds_model_payload(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        board = build_decision_board(session)

        html = render_web_html(board)

        self.assertIn("agent-foundry-web-model", html)
        self.assertIn("AI 公众号写作助手", html)
        self.assertIn("Impact Preview", html)


if __name__ == "__main__":
    unittest.main()
