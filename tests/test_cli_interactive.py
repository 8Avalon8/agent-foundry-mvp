from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_foundry.cli import main


class CLIInteractiveTest(unittest.TestCase):
    def test_new_interactive_parses_ids_indices_inputs_and_saves_session(self) -> None:
        answers = iter(
            [
                "review_focus=1,3",
                "2",
                "y",
                "3",
                "",
                "y",
                "4",
                "src/**",
                "3",
                "python3 -m unittest",
                "patch_policy=3",
                "1",
                "2",
                "n",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
                with patch("sys.stdout", new=io.StringIO()):
                    rc = main(
                        [
                            "new",
                            "我想做一个 SVN Review Agent，帮我审查 diff",
                            "--interactive",
                            "--output",
                            tmp,
                        ]
                    )

            self.assertEqual(rc, 0)
            session_path = next((Path(tmp) / ".agent_foundry_sessions").glob("session_*.json"))
            session = json.loads(session_path.read_text(encoding="utf-8"))
            decisions = session["decisions"]

            self.assertEqual(decisions["review_focus"]["value"], ["bug_risk", "test_impact"])
            self.assertEqual(decisions["lifecycle"]["value"], "scheduled")
            self.assertEqual(decisions["autonomy_level"]["value"], "L2")
            self.assertEqual(decisions["context_scope"]["value"], "custom")
            self.assertEqual(decisions["context_scope"]["inputs"]["context_custom_scope"], "src/**")
            self.assertEqual(decisions["run_tests"]["value"], "allow_whitelist")
            self.assertEqual(decisions["run_tests"]["inputs"]["test_command_whitelist"], "python3 -m unittest")
            self.assertEqual(decisions["test_command_whitelist"]["value"], "python3 -m unittest")
            self.assertEqual(decisions["patch_policy"]["value"], "write_patch_ask")
            self.assertEqual(decisions["patch_write_strategy"]["value"], "diff_review")
            self.assertEqual(decisions["source_modify_policy"]["value"], "ask")
            self.assertEqual(session["current_stage"], "tool_permissions")

    def test_new_interactive_can_resume_saved_session(self) -> None:
        first_answers = iter(
            [
                "",
                "",
                "y",
                "",
                "",
                "y",
                "",
                "",
                "",
                "",
                "n",
            ]
        )
        resume_answers = iter(
            [
                "y",
                "1",
                "2",
                "n",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("builtins.input", side_effect=lambda _prompt="": next(first_answers)):
                with patch("sys.stdout", new=io.StringIO()):
                    main(
                        [
                            "new",
                            "我想做一个 SVN Review Agent，帮我审查 diff",
                            "--interactive",
                            "--output",
                            tmp,
                        ]
                    )
            session_path = next((Path(tmp) / ".agent_foundry_sessions").glob("session_*.json"))

            with patch("builtins.input", side_effect=lambda _prompt="": next(resume_answers)):
                with patch("sys.stdout", new=io.StringIO()):
                    rc = main(["new", "--session", str(session_path), "--interactive", "--output", tmp])

            self.assertEqual(rc, 0)
            session = json.loads(session_path.read_text(encoding="utf-8"))
            decisions = session["decisions"]
            self.assertEqual(decisions["finding_feedback"]["value"], "inline_labels")
            self.assertEqual(decisions["approval_style"]["value"], "risk_card_with_reason")
            self.assertEqual(session["current_stage"], "feedback_protocol")


if __name__ == "__main__":
    unittest.main()
