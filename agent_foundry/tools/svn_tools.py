from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SVNToolError(RuntimeError):
    message: str
    command: List[str] | None = None
    returncode: int | None = None
    stderr: str = ""

    def __str__(self) -> str:
        detail = f" stderr={self.stderr.strip()}" if self.stderr else ""
        return f"{self.message}{detail}"


def find_svn_working_copy_root(path: Path) -> Path:
    start = path.resolve()
    cwd = start if start.is_dir() else start.parent
    if _has_fixture_marker(cwd):
        return _fixture_root(cwd)
    try:
        result = _run_svn(["svn", "info"], cwd=cwd)
    except SVNToolError as exc:
        fixture = _find_fixture_root(cwd)
        if fixture is not None:
            return fixture
        raise SVNToolError(f"Not an SVN working copy: {cwd}", command=exc.command, returncode=exc.returncode, stderr=exc.stderr) from exc
    for line in result.splitlines():
        if line.lower().startswith("working copy root path:"):
            return Path(line.split(":", 1)[1].strip()).resolve()
    return cwd


def run_svn_diff(repo_path: Path, paths: Optional[List[str]] = None) -> str:
    root = find_svn_working_copy_root(repo_path)
    fixture_diff = root / ".agent_foundry_fake_svn_diff"
    if fixture_diff.exists():
        return fixture_diff.read_text(encoding="utf-8")
    args = ["svn", "diff"]
    target_paths = paths if paths is not None else _default_target_paths(root, repo_path)
    for item in target_paths:
        args.append(_safe_relative_path(root, item))
    return _run_svn(args, cwd=root)


def run_svn_status(repo_path: Path) -> str:
    root = find_svn_working_copy_root(repo_path)
    fixture_status = root / ".agent_foundry_fake_svn_status"
    if fixture_status.exists():
        return fixture_status.read_text(encoding="utf-8")
    args = ["svn", "status"]
    for item in _default_target_paths(root, repo_path):
        args.append(_safe_relative_path(root, item))
    return _run_svn(args, cwd=root)


def parse_changed_files_from_diff(diff_text: str) -> List[str]:
    files: List[str] = []
    for raw in diff_text.splitlines():
        line = raw.strip()
        if line.startswith("Index: "):
            candidate = line.split("Index: ", 1)[1].strip()
        elif line.startswith("diff --git "):
            parts = line.split()
            candidate = parts[3][2:] if len(parts) >= 4 and parts[3].startswith("b/") else ""
        else:
            continue
        if candidate and candidate not in files:
            files.append(candidate.replace("\\", "/"))
    return files


def read_changed_file_context(repo_path: Path, changed_files: List[str], max_bytes_per_file: int = 20000) -> Dict[str, str]:
    root = find_svn_working_copy_root(repo_path)
    result: Dict[str, str] = {}
    for changed_file in changed_files:
        rel = _safe_relative_path(root, changed_file)
        target = (root / rel).resolve()
        if not target.exists() or not target.is_file():
            result[changed_file] = ""
            continue
        with target.open("rb") as handle:
            data = handle.read(max_bytes_per_file)
        result[changed_file] = data.decode("utf-8", errors="replace")
    return result


def _run_svn(args: List[str], *, cwd: Path, timeout: int = 20) -> str:
    try:
        completed = subprocess.run(args, cwd=str(cwd), timeout=timeout, capture_output=True, text=True, shell=False)
    except subprocess.TimeoutExpired as exc:
        raise SVNToolError("SVN command timed out", command=args, stderr=str(exc)) from exc
    except OSError as exc:
        raise SVNToolError("SVN command failed to start", command=args, stderr=str(exc)) from exc
    if completed.returncode != 0:
        raise SVNToolError("SVN command failed", command=args, returncode=completed.returncode, stderr=completed.stderr)
    return completed.stdout


def _safe_relative_path(root: Path, raw: str) -> str:
    if not raw or Path(raw).is_absolute():
        raise SVNToolError(f"Unsafe path outside SVN working copy: {raw}")
    target = (root / raw).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise SVNToolError(f"Unsafe path outside SVN working copy: {raw}") from exc
    return raw.replace("\\", "/")


def _default_target_paths(root: Path, repo_path: Path) -> List[str]:
    target = repo_path.resolve()
    root_resolved = root.resolve()
    try:
        rel = target.relative_to(root_resolved)
    except ValueError:
        return []
    if str(rel) in {"", "."}:
        return []
    return [rel.as_posix()]


def _has_fixture_marker(path: Path) -> bool:
    return (path / ".agent_foundry_fake_svn_diff").exists() or (path / ".svn").exists()


def _fixture_root(path: Path) -> Path:
    return path.resolve()


def _find_fixture_root(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in [current, *current.parents]:
        if _has_fixture_marker(candidate):
            return candidate
    return None
