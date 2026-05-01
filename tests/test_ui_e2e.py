from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_foundry.renderers.ui_demo import build_ui_demo


class UIE2EDemoTest(unittest.TestCase):
    def test_ui_demo_generates_events_session_agentspec_and_dry_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = build_ui_demo(root)

            self.assertEqual(len(manifest["scenarios"]), 2)
            for scenario in manifest["scenarios"]:
                scenario_dir = root / scenario["id"]
                self.assertTrue((root / scenario["events"]).exists())
                self.assertTrue((root / scenario["final_session"]).exists())
                self.assertTrue((root / scenario["agent_spec"]).exists())
                self.assertTrue((root / scenario["web_view_model"]).exists())
                self.assertTrue((root / scenario["a2ui_tree"]).exists())
                self.assertTrue((root / scenario["agent_dir"] / "agent.yaml").exists())
                self.assertTrue((root / scenario["dry_run"] / "permission_checks.json").exists())
                checks_data = json.loads((root / scenario["dry_run"] / "permission_checks.json").read_text(encoding="utf-8"))
                checks = checks_data["checks"]
                high_allowed = [entry for entry in checks if entry["status"] == "allowed" and entry["risk"] in {"high", "critical"}]
                self.assertEqual(high_allowed, [])
                self.assertTrue((scenario_dir / "initial_web_view_model.json").exists())

            review_run = root / manifest["scenarios"][0]["dry_run"]
            writing_run = root / manifest["scenarios"][1]["dry_run"]
            self.assertTrue((review_run / "feedback_requests.json").exists())
            self.assertTrue((review_run / "rule_patch_proposal.md").exists())
            self.assertTrue((writing_run / "topic_selection_request.json").exists())
            self.assertTrue((writing_run / "style_rule_patch.md").exists())


if __name__ == "__main__":
    unittest.main()
