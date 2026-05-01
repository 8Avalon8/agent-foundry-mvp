from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import create_session


class AgentSpecCompilerSafetyTest(unittest.TestCase):
    def test_review_defaults_do_not_allow_high_risk_actions(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)

        self.assertEqual(spec["tool_policy"]["shell.run_tests"]["permission"], "ask")
        self.assertEqual(spec["tool_policy"]["fs.write_patch"]["permission"], "deny")
        self.assertEqual(spec["tool_policy"]["fs.modify_source"]["permission"], "ask")
        self.assertEqual(spec["tool_policy"]["svn.commit"]["permission"], "deny")
        self.assertTrue(spec["memory"]["update_requires_approval"])
        self.assertTrue(spec["memory"]["rule_patch"]["requires_approval"])

    def test_allow_list_tests_require_explicit_user_confirmation(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        session.apply_decision("run_tests", "allow_whitelist", source="recommended_accepted")
        self.assertEqual(compile_agentspec(session)["tool_policy"]["shell.run_tests"]["permission"], "ask")

        session.apply_decision("run_tests", "allow_whitelist", source="user_selected")
        self.assertEqual(compile_agentspec(session)["tool_policy"]["shell.run_tests"]["permission"], "allow")

    def test_writing_publish_defaults_to_deny_until_user_confirms(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        spec = compile_agentspec(session)

        self.assertEqual(spec["tool_policy"]["fs.write_draft"]["permission"], "ask")
        self.assertEqual(spec["tool_policy"]["wechat.publish"]["permission"], "deny")
        self.assertTrue(spec["memory"]["update_requires_approval"])
        self.assertTrue(spec["memory"]["style_patch"]["requires_approval"])

        session.apply_decision("publish_policy", "explicit_confirmation", source="user_selected")
        spec = compile_agentspec(session)
        self.assertEqual(spec["tool_policy"]["wechat.publish"]["permission"], "ask")

    def test_all_tool_policy_entries_have_permission_and_risk(self) -> None:
        for goal in [
            "我想做一个 SVN Review Agent，帮我审查 diff",
            "我想做一个微信公众号写作 Agent，帮我把素材变成文章",
        ]:
            spec = compile_agentspec(create_session(goal))
            for policy in spec["tool_policy"].values():
                self.assertIn(policy["permission"], {"allow", "ask", "deny"})
                self.assertIn("risk", policy)

    def test_agentspec_schema_requires_policy_risk_and_memory_approval(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "agent_foundry" / "schemas" / "agentspec.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        tool_policy_item = schema["properties"]["tool_policy"]["additionalProperties"]
        self.assertIn("permission", tool_policy_item["required"])
        self.assertIn("risk", tool_policy_item["required"])
        self.assertEqual(schema["properties"]["memory"]["properties"]["update_requires_approval"]["const"], True)


if __name__ == "__main__":
    unittest.main()
