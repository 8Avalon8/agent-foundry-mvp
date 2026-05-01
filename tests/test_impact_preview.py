from __future__ import annotations

import unittest

from agent_foundry.builder.decision_board import create_session
from agent_foundry.builder.impact_preview import build_spec_diff_preview, impact_items_to_mapping, impact_preview_as_diff
from agent_foundry.builder.models import PreSpecSession


class ImpactPreviewDiffTest(unittest.TestCase):
    def test_spec_diff_preview_covers_policy_feedback_memory_and_outputs(self) -> None:
        before = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        before.apply_decision("run_tests", "deny")
        before.apply_decision("patch_policy", "deny")
        before.apply_decision("finding_feedback", "free_chat")
        before.apply_decision("memory_policy", "no_long_term")
        before.apply_decision("output_format", "markdown_report")

        after = PreSpecSession.from_dict(before.to_dict())
        after.apply_decision("run_tests", "ask")
        after.apply_decision("patch_policy", "write_patch_ask")
        after.apply_decision("finding_feedback", "inline_labels")
        after.apply_decision("memory_policy", "approved_rule_patch")
        after.apply_decision("output_format", "html_and_markdown")

        items = build_spec_diff_preview(before, after)
        mapping = impact_items_to_mapping(items)

        self.assertEqual(mapping["tool_policy.shell.run_tests.permission"], {"before": "deny", "after": "ask"})
        self.assertEqual(mapping["tool_policy.fs.write_patch.permission"], {"before": "deny", "after": "ask"})
        self.assertEqual(mapping["human_feedback.finding_feedback.mode"], {"before": "free_chat", "after": "inline_labels"})
        self.assertEqual(mapping["memory.update_policy"], {"before": "no_long_term", "after": "approved_rule_patch"})
        self.assertIn("review_report.html", mapping["output.artifacts"]["after"])

    def test_diff_renderer_uses_before_after_style(self) -> None:
        before = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        before.apply_decision("run_tests", "deny")
        after = PreSpecSession.from_dict(before.to_dict())
        after.apply_decision("run_tests", "ask")

        text = impact_preview_as_diff(build_spec_diff_preview(before, after))

        self.assertIn("tool_policy.shell.run_tests:", text)
        self.assertIn("- permission: deny", text)
        self.assertIn("+ permission: ask", text)


if __name__ == "__main__":
    unittest.main()
