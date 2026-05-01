from __future__ import annotations

import unittest

from agent_foundry.builder.decision_board import build_decision_board, create_session


def question_ids(board) -> list[str]:
    return [question.id for question in board.questions]


class DecisionGraphVisibilityTest(unittest.TestCase):
    def test_review_hides_test_whitelist_when_tests_are_denied(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        session.apply_decision("run_tests", "deny")

        board = build_decision_board(session)

        self.assertNotIn("test_command_whitelist", question_ids(board))
        self.assertNotIn("test_command_whitelist", session.unresolved)

    def test_review_shows_test_whitelist_when_tests_use_allow_list(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        session.apply_decision("run_tests", "allow_whitelist")

        board = build_decision_board(session)

        self.assertIn("test_command_whitelist", question_ids(board))
        self.assertIn("test_command_whitelist", session.unresolved)

    def test_review_hides_patch_strategy_when_patch_is_denied(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        session.apply_decision("patch_policy", "deny")

        board = build_decision_board(session)

        self.assertNotIn("patch_write_strategy", question_ids(board))
        self.assertNotIn("patch_write_strategy", session.unresolved)

    def test_review_shows_patch_strategy_when_patch_can_be_written(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.current_stage = "tool_permissions"
        session.apply_decision("patch_policy", "write_patch_ask")

        board = build_decision_board(session)

        self.assertIn("patch_write_strategy", question_ids(board))
        self.assertIn("patch_write_strategy", session.unresolved)

    def test_writing_hides_publish_approval_detail_when_never_publishing(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        session.current_stage = "tool_permissions"
        session.apply_decision("publish_policy", "never_publish")

        board = build_decision_board(session)

        self.assertNotIn("publish_approval_detail", question_ids(board))
        self.assertNotIn("publish_approval_detail", session.unresolved)

    def test_writing_shows_publish_approval_detail_when_publish_requires_confirmation(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        session.current_stage = "tool_permissions"
        session.apply_decision("publish_policy", "explicit_confirmation")

        board = build_decision_board(session)

        self.assertIn("publish_approval_detail", question_ids(board))
        self.assertIn("publish_approval_detail", session.unresolved)


if __name__ == "__main__":
    unittest.main()
