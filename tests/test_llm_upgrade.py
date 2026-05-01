from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from agent_foundry.builder.decision_board import apply_recommended_defaults, build_decision_board
from agent_foundry.builder.decision_board import create_session, load_session, save_session
from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.builder.llm_builder import apply_natural_language_update, create_session_with_llm
from agent_foundry.builder.models import DecisionQuestion
from agent_foundry.llm.mock_provider import MockLLMProvider
from agent_foundry.llm.provider import provider_from_name
from agent_foundry.runtime.dry_run import dry_run


class LLMUpgradeTest(unittest.TestCase):
    def test_mock_llm_creates_dynamic_prespec_question(self) -> None:
        provider = MockLLMProvider()
        session = create_session_with_llm("我想做一个 SVN Review Agent", provider=provider)
        self.assertEqual(session.metadata["builder_mode"], "llm")
        self.assertEqual(session.selected_preset, "controlled_semi_auto")
        session.current_stage = "feedback_protocol"
        board = build_decision_board(session)
        question_ids = [q.id for q in board.questions]
        self.assertIn("evidence_style", question_ids)

    def test_mock_llm_compile_and_dry_run(self) -> None:
        provider = MockLLMProvider()
        session = create_session_with_llm("我想做一个 SVN Review Agent，帮我审查 diff", provider=provider)
        apply_recommended_defaults(session, include_all_stages=True)
        spec = compile_agentspec(session)
        self.assertIn("custom_decisions", spec)
        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp))
            (agent_dir / "prespec_session.json").write_text(json.dumps(session.to_dict(), ensure_ascii=False), encoding="utf-8")
            run_dir = dry_run(agent_dir, provider=provider)
            self.assertTrue((run_dir / "review_report.md").exists())
            metadata = json.loads((run_dir / "llm_dry_run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["mode"], "llm")

    def test_natural_language_update(self) -> None:
        provider = MockLLMProvider()
        session = create_session_with_llm("我想做一个 SVN Review Agent", provider=provider)
        result = apply_natural_language_update(session, provider, "可以读项目上下文，但不能自动写文件；生成 patch 必须让我确认")
        self.assertTrue(result["applied"])
        self.assertEqual(session.get_value("context_scope"), "project_search")
        self.assertEqual(session.get_value("source_modify_policy"), "deny")
        self.assertEqual(session.get_value("patch_policy"), "write_patch_ask")

    def test_openai_provider_uses_openai_base_url(self) -> None:
        captured = {}

        class FakeOpenAI:
            def __init__(self, **kwargs) -> None:
                captured.update(kwargs)

        fake_openai_module = SimpleNamespace(OpenAI=FakeOpenAI)
        env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://gateway.example/v1",
            "AGENT_FOUNDRY_OPENAI_MODEL": "test-model",
        }
        with patch.dict(sys.modules, {"openai": fake_openai_module}):
            with patch.dict(os.environ, env, clear=False):
                provider = provider_from_name("openai")

        self.assertIsNotNone(provider)
        self.assertEqual(provider.model, "test-model")
        self.assertEqual(captured["api_key"], "test-key")
        self.assertEqual(captured["base_url"], "https://gateway.example/v1")

    def test_decision_question_accepts_type_alias_and_writes_both_names(self) -> None:
        question = DecisionQuestion.from_dict(
            {
                "id": "run_tests",
                "title": "是否允许运行测试命令？",
                "type": "single_choice",
                "stage": "tool_permissions",
                "recommended": "ask",
                "options": [{"id": "ask", "label": "每次运行前询问"}],
                "affects": ["tool_policy.shell.run_tests"],
            }
        )
        data = question.to_dict()
        self.assertEqual(question.input_type, "single_choice")
        self.assertEqual(data["input_type"], "single_choice")
        self.assertEqual(data["type"], "single_choice")

    def test_session_round_trip_preserves_decisions_inputs_and_unresolved(self) -> None:
        session = create_session("我想做一个 SVN Review Agent")
        self.assertIn("run_tests", session.unresolved)
        session.apply_decision("run_tests", "allow_whitelist", inputs={"test_command_whitelist": "python3 -m unittest"})
        self.assertNotIn("run_tests", session.unresolved)

        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp) / "session.json"
            save_session(session, session_path)
            loaded = load_session(session_path)

        self.assertEqual(loaded.get_value("run_tests"), "allow_whitelist")
        self.assertEqual(loaded.get_inputs("run_tests")["test_command_whitelist"], "python3 -m unittest")
        self.assertEqual(loaded.unresolved, session.unresolved)

    def test_schema_declares_question_constraints_needed_by_docs(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "agent_foundry" / "schemas" / "decision_question.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        for field in [
            "required",
            "recommended",
            "recommendation_reason",
            "risk_level",
            "options",
            "affects",
        ]:
            self.assertIn(field, schema["required"])
            self.assertIn(field, schema["properties"])
        requires_input = schema["properties"]["options"]["items"]["properties"]["requires_input"]
        self.assertIn("id", requires_input["required"])
        self.assertIn("type", requires_input["required"])
        self.assertIn("placeholder", requires_input["required"])


if __name__ == "__main__":
    unittest.main()
