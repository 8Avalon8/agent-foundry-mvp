from __future__ import annotations

import unittest

from agent_foundry.builder.decision_board import build_decision_board, create_session
from agent_foundry.renderers.a2ui_renderer import board_to_a2ui_tree


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


class A2UIRendererTest(unittest.TestCase):
    def test_a2ui_tree_preserves_risk_recommendation_requires_input_and_affects(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        board = build_decision_board(session)

        tree = board_to_a2ui_tree(board)

        nodes = list(walk(tree["root"]))
        decision_nodes = [node for node in nodes if node["type"] == "DecisionCard"]
        self.assertTrue(decision_nodes)
        run_tests = next(node for node in decision_nodes if node["props"]["question_id"] == "run_tests")
        self.assertEqual(run_tests["props"]["risk_level"], "medium")
        self.assertEqual(run_tests["props"]["recommendation"]["value"], "ask")
        self.assertEqual(run_tests["props"]["requires_input"][0]["id"], "test_command_whitelist")
        self.assertIn("tool_policy.shell.run_tests", run_tests["props"]["affects"])

    def test_a2ui_action_payload_schema_is_session_scoped(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        board = build_decision_board(session)

        tree = board_to_a2ui_tree(board)

        schema = tree["action_payload_schema"]
        self.assertEqual(schema["properties"]["session_id"]["const"], session.id)
        self.assertIn("select_option", schema["properties"]["action"]["enum"])
        self.assertIn("use_recommended", schema["properties"]["action"]["enum"])
        self.assertIn("confirm_stage", schema["properties"]["action"]["enum"])


if __name__ == "__main__":
    unittest.main()
