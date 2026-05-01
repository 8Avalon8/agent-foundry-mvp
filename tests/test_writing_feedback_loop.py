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


class WritingFeedbackLoopTest(unittest.TestCase):
    def test_writing_dry_run_outputs_topic_article_package_and_style_patch(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp), prespec_session=session.to_dict())
            run_dir = dry_run(agent_dir)

            topics = json.loads((run_dir / "topic_options.json").read_text(encoding="utf-8"))
            request = json.loads((run_dir / "topic_selection_request.json").read_text(encoding="utf-8"))

            self.assertTrue((run_dir / "topic_options.md").exists())
            self.assertTrue((run_dir / "outline.md").exists())
            self.assertTrue((run_dir / "article.md").exists())
            self.assertTrue((run_dir / "publish_package.json").exists())
            self.assertTrue((run_dir / "style_rule_patch.md").exists())

        self.assertGreaterEqual(len(topics), 3)
        self.assertLessEqual(len(topics), 5)
        self.assertEqual(request["type"], "topic_selection")

    def test_writing_feedback_generates_style_patch_without_silent_learning(self) -> None:
        session = create_session("我想做一个微信公众号写作 Agent，帮我把素材变成文章")
        spec = compile_agentspec(session)

        with tempfile.TemporaryDirectory() as tmp:
            agent_dir = generate_agent_files(spec, Path(tmp), prespec_session=session.to_dict())
            style_rules_before = (agent_dir / "style_rules.md").read_text(encoding="utf-8")
            run_dir = dry_run(agent_dir)

            with patch("sys.stdout", new=io.StringIO()):
                rc = main(
                    [
                        "writing-feedback",
                        str(run_dir),
                        "--topic",
                        "2",
                        "--style-feedback",
                        "标题更克制一点，多保留真实工作流细节",
                    ]
                )

            selected = json.loads((run_dir / "selected_topic.json").read_text(encoding="utf-8"))
            proposal = (run_dir / "style_rule_patch.md").read_text(encoding="utf-8")
            style_rules_after = (agent_dir / "style_rules.md").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertIn("标题更克制", selected["style_feedback"])
        self.assertIn("必须经用户确认", proposal)
        self.assertIn("候选补丁", proposal)
        self.assertEqual(style_rules_after, style_rules_before)


if __name__ == "__main__":
    unittest.main()
