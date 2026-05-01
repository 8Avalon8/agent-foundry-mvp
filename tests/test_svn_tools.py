from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_foundry.tools.svn_tools import (
    SVNToolError,
    find_svn_working_copy_root,
    parse_changed_files_from_diff,
    read_changed_file_context,
    run_svn_diff,
    run_svn_status,
)


class SVNToolsTest(unittest.TestCase):
    def test_fake_svn_diff_returns_diff_text(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")

        diff = run_svn_diff(fixture)

        self.assertIn("Index: src/UserProfileService.java", diff)

    def test_fake_svn_status_works(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")

        status = run_svn_status(fixture)

        self.assertIn("M       src/UserProfileService.java", status)

    def test_parse_changed_files_from_diff(self) -> None:
        files = parse_changed_files_from_diff("Index: src/A.py\nIndex: src/B.py\n")

        self.assertEqual(files, ["src/A.py", "src/B.py"])

    def test_find_root_uses_svn_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_run(args, cwd, timeout, capture_output, text, shell):
                self.assertEqual(args, ["svn", "info"])
                self.assertFalse(shell)
                return subprocess.CompletedProcess(args, 0, stdout=f"Working Copy Root Path: {root}\n", stderr="")

            with patch("agent_foundry.tools.svn_tools.subprocess.run", side_effect=fake_run):
                self.assertEqual(find_svn_working_copy_root(root), root.resolve())

    def test_diff_scopes_to_subdirectory_inside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subdir = root / "trunk" / "Project"
            subdir.mkdir(parents=True)
            calls = []

            def fake_run(args, cwd, timeout, capture_output, text, shell):
                calls.append(args)
                if args == ["svn", "info"]:
                    return subprocess.CompletedProcess(args, 0, stdout=f"Working Copy Root Path: {root}\n", stderr="")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

            with patch("agent_foundry.tools.svn_tools.subprocess.run", side_effect=fake_run):
                run_svn_diff(subdir)

        self.assertEqual(calls[-1], ["svn", "diff", "trunk/Project"])

    def test_non_svn_working_copy_gives_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "agent_foundry.tools.svn_tools.subprocess.run",
                return_value=subprocess.CompletedProcess(["svn", "info"], 1, stdout="", stderr="not a working copy"),
            ):
                with self.assertRaisesRegex(SVNToolError, "Not an SVN working copy"):
                    find_svn_working_copy_root(Path(tmp))

    def test_svn_command_timeout_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(cmd=["svn", "info"], timeout=20)

            with patch("agent_foundry.tools.svn_tools.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(SVNToolError, "Not an SVN working copy"):
                    find_svn_working_copy_root(root)

    def test_read_context_blocks_path_traversal(self) -> None:
        fixture = Path("tests/fixtures/fake_svn_working_copy")

        with self.assertRaisesRegex(SVNToolError, "Unsafe path"):
            read_changed_file_context(fixture, ["../secret.txt"])


if __name__ == "__main__":
    unittest.main()
