from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import create_session
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.cli import main
from agent_foundry.llm.mock_provider import MockLLMProvider
from agent_foundry.runtime.review_runtime import run_review_svn


class ReviewRuntimeSVNTest(unittest.TestCase):
    def test_review_svn_generates_full_run_directory(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            run_dir = run_review_svn(fixture, agent_dir, root / "runs", provider=MockLLMProvider())

            expected = [
                "review_report.md",
                "findings.json",
                "feedback_requests.json",
                "test_suggestions.md",
                "rule_patch_proposal.md",
                "run_log.json",
                "permission_checks.json",
                "context_snapshot.json",
                "pending_approvals.json",
                "approval_log.jsonl",
                "run_state.json",
            ]
            for name in expected:
                self.assertTrue((run_dir / name).exists(), name)
            approvals = json.loads((run_dir / "pending_approvals.json").read_text(encoding="utf-8"))
            context = json.loads((run_dir / "context_snapshot.json").read_text(encoding="utf-8"))

        self.assertEqual(approvals[0]["id"], "approval_shell_run_tests")
        self.assertIn("src/UserProfileService.java", context["changed_files"])
        self.assertIn("loaded_memory_files", context)

    def test_review_svn_passes_requested_path_to_svn_diff_and_status(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_diff", return_value="Index: src/UserProfileService.java\n") as mocked_diff:
                with patch("agent_foundry.runtime.review_runtime.run_svn_status", return_value=""):
                    run_review_svn(fixture, agent_dir, root / "runs")

        mocked_diff.assert_called_once_with(fixture)

    def test_ask_permission_generates_pending_approval_and_does_not_execute(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        spec["tool_policy"]["svn.diff"]["permission"] = "ask"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_diff") as mocked_diff:
                run_dir = run_review_svn(fixture, agent_dir, root / "runs")
            approvals = json.loads((run_dir / "pending_approvals.json").read_text(encoding="utf-8"))

        mocked_diff.assert_not_called()
        self.assertEqual(approvals[0]["tool"], "svn.diff")

    def test_deny_permission_refuses_and_logs_reason(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        spec["tool_policy"]["svn.diff"]["permission"] = "deny"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_diff") as mocked_diff:
                run_dir = run_review_svn(fixture, agent_dir, root / "runs")
            run_log = json.loads((run_dir / "run_log.json").read_text(encoding="utf-8"))

        mocked_diff.assert_not_called()
        self.assertIn("denied by tool_policy", run_log["errors"][0])

    def test_denied_svn_status_is_not_executed(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        spec["tool_policy"]["svn.status"]["permission"] = "deny"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_status") as mocked_status:
                run_dir = run_review_svn(fixture, agent_dir, root / "runs")
            checks = json.loads((run_dir / "permission_checks.json").read_text(encoding="utf-8"))

        mocked_status.assert_not_called()
        self.assertEqual([item for item in checks["checks"] if item["tool"] == "svn.status"][0]["status"], "denied")

    def test_second_review_loads_learned_rules_and_records_it(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            run_dir = run_review_svn(fixture, agent_dir, root / "runs")
            with patch("sys.stdout", new=io.StringIO()):
                main(["memory-apply", str(agent_dir), str(run_dir), "--patch", "rule_patch_proposal.md"])
            second_run = run_review_svn(fixture, agent_dir, root / "runs")
            run_log = json.loads((second_run / "run_log.json").read_text(encoding="utf-8"))

        self.assertTrue(run_log["loaded_memory_files"])
        self.assertTrue(run_log["loaded_memory_files"][0]["path"].endswith("learned_rules.md"))

    def test_cli_review_svn_command_works(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("sys.stdout", new=io.StringIO()):
                rc = main(["review-svn", str(fixture), "--agent", str(agent_dir), "--output", str(root / "runs"), "--llm-provider", "mock"])
            runs = list((root / "runs").glob("review_svn_*"))

        self.assertEqual(rc, 0)
        self.assertEqual(len(runs), 1)

    def test_large_diff_is_truncated_before_llm_prompt(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        class CapturingProvider:
            name = "capture"

            def __init__(self) -> None:
                self.prompt = ""

            def complete_json(self, *, system_prompt, user_prompt, schema, schema_name, temperature=0.2):
                self.prompt = user_prompt
                return {
                    "report_markdown": "# Report\n",
                    "findings": [],
                    "test_suggestions": [],
                    "rule_patch_markdown": "# Rule Patch Proposal\n",
                }

        provider = CapturingProvider()
        large_diff = "Index: src/UserProfileService.java\n" + ("+x\n" * 30000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_diff", return_value=large_diff):
                run_dir = run_review_svn(fixture, agent_dir, root / "runs", provider=provider)  # type: ignore[arg-type]
            run_log = json.loads((run_dir / "run_log.json").read_text(encoding="utf-8"))

        self.assertLess(len(provider.prompt), len(large_diff))
        self.assertTrue(run_log["diff"]["truncated_for_llm"])

    def test_file_context_is_capped_for_large_change_sets(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        many_files = [f"src/File{i}.java" for i in range(70)]
        diff = "\n".join(f"Index: {item}" for item in many_files)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = generate_agent_files(spec, root)
            with patch("agent_foundry.runtime.review_runtime.run_svn_diff", return_value=diff):
                run_dir = run_review_svn(fixture, agent_dir, root / "runs")
            snapshot = json.loads((run_dir / "context_snapshot.json").read_text(encoding="utf-8"))

        self.assertEqual(len(snapshot["file_context"]), 50)
        self.assertEqual(snapshot["file_context_omitted"], 20)


if __name__ == "__main__":
    unittest.main()
