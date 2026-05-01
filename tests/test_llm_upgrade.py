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
from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.builder.llm_builder import apply_natural_language_update, create_session_with_llm
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


if __name__ == "__main__":
    unittest.main()
