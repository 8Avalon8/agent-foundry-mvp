from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_foundry.runtime.approval_store import add_pending_approval, record_approval_decision
from agent_foundry.runtime.review_runtime import resume_review_run


class RunStateApprovalsTest(unittest.TestCase):
    def test_approve_writes_approval_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            add_pending_approval(
                run_dir,
                {
                    "id": "approval_shell_run_tests",
                    "type": "approval",
                    "tool": "shell.run_tests",
                    "risk": "medium",
                    "reason": "tests require approval",
                    "payload": {},
                    "options": ["approve_once", "reject"],
                },
            )

            entry = record_approval_decision(run_dir, "approval_shell_run_tests", "reject")
            approvals = json.loads((run_dir / "pending_approvals.json").read_text(encoding="utf-8"))
            log = (run_dir / "approval_log.jsonl").read_text(encoding="utf-8")

        self.assertEqual(entry["decision"], "reject")
        self.assertEqual(approvals[0]["status"], "rejected")
        self.assertIn('"approval_id": "approval_shell_run_tests"', log)

    def test_resume_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "pending_approvals.json").write_text("[]", encoding="utf-8")

            first = resume_review_run(run_dir)
            second = resume_review_run(run_dir)

        self.assertEqual(first["status"], "no_pending_approvals")
        self.assertEqual(second["status"], "no_pending_approvals")


if __name__ == "__main__":
    unittest.main()
