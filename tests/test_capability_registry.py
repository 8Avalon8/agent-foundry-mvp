from __future__ import annotations

import unittest

from agent_foundry.runtime.capability_registry import CapabilityResolutionError, resolve_required_capabilities


class CapabilityRegistryTest(unittest.TestCase):
    def test_review_capabilities_map_to_registered_tools(self) -> None:
        spec = {
            "tools": {
                "required_capabilities": [
                    "read_svn_diff",
                    "read_svn_status",
                    "parse_diff_files",
                    "read_files",
                    "search_code",
                    "generate_review_report",
                    "collect_human_feedback",
                    "propose_rule_patch",
                    "apply_memory_patch",
                ]
            }
        }

        resolved = resolve_required_capabilities(spec)

        self.assertEqual(len(resolved), 9)
        self.assertEqual(resolved[0].tool.tool_id, "svn.diff")

    def test_missing_capability_fails_clearly(self) -> None:
        with self.assertRaisesRegex(CapabilityResolutionError, "Missing tool for capability"):
            resolve_required_capabilities({"tools": {"required_capabilities": ["invent_arbitrary_tool"]}})


if __name__ == "__main__":
    unittest.main()
