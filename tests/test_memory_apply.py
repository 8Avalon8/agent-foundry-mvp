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


class MemoryApplyTest(unittest.TestCase):
    def test_memory_review_apply_and_reject(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            run_dir = root / "runs" / "review_svn_test"
            run_dir.mkdir(parents=True)
            (run_dir / "rule_patch_proposal.md").write_text("# Rule Patch Proposal\n\n```diff\n+ remember this\n```\n", encoding="utf-8")

            with patch("sys.stdout", new=io.StringIO()) as stdout:
                self.assertEqual(main(["memory-review", str(run_dir)]), 0)
                review_output = stdout.getvalue()
            self.assertIn("remember this", review_output)

            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(main(["memory-apply", str(agent_dir), str(run_dir), "--patch", "rule_patch_proposal.md"]), 0)
            learned_rules = (agent_dir / "learned_rules.md").read_text(encoding="utf-8")
            memory_log = (agent_dir / "memory_log.jsonl").read_text(encoding="utf-8")

            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(main(["memory-reject", str(agent_dir), str(run_dir), "--reason", "too broad"]), 0)
            rejected = json.loads((agent_dir / "rejected_rule_patches.jsonl").read_text(encoding="utf-8").splitlines()[0])

        self.assertIn("remember this", learned_rules)
        self.assertIn('"approved_by_user": true', memory_log)
        self.assertEqual(rejected["reason"], "too broad")


if __name__ == "__main__":
    unittest.main()
