from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import create_session
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.cli import main
from agent_foundry.runtime.dry_run import dry_run


class ReviewFeedbackLoopTest(unittest.TestCase):
    def test_review_dry_run_outputs_feedback_requests_and_rule_patch_candidate(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp), prespec_session=session.to_dict())
            run_dir = dry_run(agent_dir)

            self.assertTrue((run_dir / "review_report.md").exists())
            self.assertTrue((run_dir / "findings.json").exists())
            self.assertTrue((run_dir / "test_suggestions.md").exists())
            self.assertTrue((run_dir / "rule_patch_proposal.md").exists())
            requests = json.loads((run_dir / "feedback_requests.json").read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(requests), 1)
        self.assertEqual(requests[0]["type"], "finding_feedback")
        self.assertIn("accepted", requests[0]["options"])
        self.assertIn("needs_more_evidence", requests[0]["options"])

    def test_feedback_command_generates_rule_patch_without_learning_silently(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp), prespec_session=session.to_dict())
            learned_rules_before = (agent_dir / "learned_rules.md").read_text(encoding="utf-8")
            run_dir = dry_run(agent_dir)
            finding_id = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))[0]["id"]

            with patch("sys.stdout", new=io.StringIO()):
                rc = main(
                    [
                        "feedback",
                        str(run_dir),
                        "--label",
                        f"{finding_id}=accepted",
                        "--reason",
                        f"{finding_id}=dry run accepted for test",
                    ]
                )

            feedback = json.loads((run_dir / "feedback_labels.json").read_text(encoding="utf-8"))
            proposal = (run_dir / "rule_patch_proposal.md").read_text(encoding="utf-8")
            learned_rules_after = (agent_dir / "learned_rules.md").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(feedback[0]["label"], "accepted")
        self.assertIn("必须经用户确认", proposal)
        self.assertIn("候选补丁", proposal)
        self.assertEqual(learned_rules_after, learned_rules_before)


if __name__ == "__main__":
    unittest.main()
