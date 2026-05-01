from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import create_session, generate_design_card
from agent_foundry.builder.file_generator import generate_agent_files


class FileGeneratorTest(unittest.TestCase):
    def test_generator_writes_stable_file_set(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)
        card = generate_design_card(session)
        expected = {
            "agent.yaml",
            "system_prompt.md",
            "runbook.md",
            "tool_policy.yaml",
            "human_feedback.yaml",
            "memory_policy.yaml",
            "eval_rubric.yaml",
            "output_schema.json",
            "prespec_session.json",
            "agent_design_card.md",
            "examples",
        }

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(
                spec,
                Path(tmp),
                prespec_session=session.to_dict(),
                design_card_markdown=card.to_markdown(),
            )
            names = {path.name for path in agent_dir.iterdir()}

        self.assertTrue(expected <= names)

    def test_generated_policy_files_match_agentspec(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp), prespec_session=session.to_dict())
            agent_yaml = yaml.safe_load((agent_dir / "agent.yaml").read_text(encoding="utf-8"))
            tool_policy = yaml.safe_load((agent_dir / "tool_policy.yaml").read_text(encoding="utf-8"))
            human_feedback = yaml.safe_load((agent_dir / "human_feedback.yaml").read_text(encoding="utf-8"))
            memory_policy = yaml.safe_load((agent_dir / "memory_policy.yaml").read_text(encoding="utf-8"))
            saved_session = json.loads((agent_dir / "prespec_session.json").read_text(encoding="utf-8"))

        self.assertEqual(agent_yaml["tool_policy"], spec["tool_policy"])
        self.assertEqual(tool_policy, spec["tool_policy"])
        self.assertEqual(human_feedback, spec["human_feedback"])
        self.assertEqual(memory_policy, spec["memory"])
        self.assertEqual(saved_session["id"], session.id)

    def test_prompts_and_runbook_include_boundaries_and_pause_points(self) -> None:
        session = create_session("我想做一个 SVN Review Agent，帮我审查 diff")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp))
            system_prompt = (agent_dir / "system_prompt.md").read_text(encoding="utf-8")
            runbook = (agent_dir / "runbook.md").read_text(encoding="utf-8")

        self.assertIn("权限和反馈边界", system_prompt)
        self.assertIn("Rule Patch / Style Patch 只能作为候选补丁", system_prompt)
        self.assertIn("## 暂停点", runbook)
        self.assertIn("shell.run_tests", runbook)


if __name__ == "__main__":
    unittest.main()
