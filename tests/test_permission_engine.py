from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import create_session
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.runtime.dry_run import dry_run
from agent_foundry.runtime.permission_engine import check_permission, permission_checks_for_spec, resolve_approval


class PermissionEngineTest(unittest.TestCase):
    def test_ask_permission_returns_standard_approval_request(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        decision = check_permission(spec, "shell.run_tests", {"command": "python3 -m unittest"})
        data = decision.to_dict()

        self.assertEqual(data["status"], "requires_approval")
        self.assertEqual(data["permission"], "ask")
        self.assertEqual(data["approval_request"]["action"], "shell.run_tests")
        self.assertEqual(data["approval_request"]["risk"], "medium")
        self.assertIn("approve_once", data["approval_request"]["options"])
        self.assertIn("reject", data["approval_request"]["options"])
        self.assertIn("show_impact", data["approval_request"]["options"])
        self.assertIn("add_to_whitelist", data["approval_request"]["options"])
        json.dumps(data, ensure_ascii=False)

    def test_deny_permission_records_reason_without_approval(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        decision = check_permission(spec, "svn.commit")

        self.assertEqual(decision.status, "denied")
        self.assertIn("denied by tool_policy", decision.reason)
        self.assertIsNone(decision.approval_request)

    def test_approval_actions_are_serializable(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        decision = check_permission(spec, "shell.run_tests", {"command": "python3 -m unittest"})

        for action in ["approve_once", "reject", "show_impact", "add_to_whitelist"]:
            result = resolve_approval(decision, action)  # type: ignore[arg-type]
            json.dumps(result, ensure_ascii=False)
            self.assertIn("status", result)

    def test_dry_run_writes_permission_checks(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp))
            run_dir = dry_run(agent_dir)
            checks = json.loads((run_dir / "permission_checks.json").read_text(encoding="utf-8"))

        self.assertEqual(checks["type"], "permission_checks")
        by_tool = {item["tool"]: item for item in checks["checks"]}
        self.assertEqual(by_tool["shell.run_tests"]["status"], "requires_approval")
        self.assertEqual(by_tool["svn.commit"]["status"], "denied")

    def test_permission_checks_for_spec_covers_all_policy_entries(self) -> None:
        spec = compile_agentspec(create_session("我想做一个 SVN Review Agent，帮我审查 diff"))
        checks = permission_checks_for_spec(spec)

        self.assertEqual(len(checks["checks"]), len(spec["tool_policy"]))


if __name__ == "__main__":
    unittest.main()
