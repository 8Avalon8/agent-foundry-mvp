from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_foundry.llm.provider import BaseLLMProvider
from agent_foundry.tools.svn_tools import (
    SVNToolError,
    find_svn_working_copy_root,
    parse_changed_files_from_diff,
    read_changed_file_context,
    run_svn_diff,
    run_svn_status,
)

from .approval_store import add_pending_approval, ensure_approval_log, load_pending_approvals, pending_count
from .capability_registry import CapabilityResolutionError, resolve_required_capabilities
from .dry_run import REVIEW_DRY_RUN_SCHEMA, analyze_diff_heuristically, load_agent_spec, propose_rule_patch, render_review_report, suggest_tests
from .feedback_engine import batch_feedback_requests
from .permission_engine import PermissionDecision, check_permission
from .run_state import mark_step, new_run_state, save_run_state


REVIEW_SYSTEM_PROMPT = """你是 Agent Foundry 的 SVN review runtime。

要求：
- 只输出符合 JSON Schema 的对象。
- 只能分析输入中的 diff、文件摘要和 learned_rules。
- 不要声称已经运行测试、提交代码或修改源码。
- finding 必须包含证据、建议、置信度和反馈选项。
- rule patch 只是候选，必须等待用户显式 memory-apply。
"""

MAX_LLM_DIFF_CHARS = 60000
MAX_CONTEXT_FILES = 50
MAX_LLM_CONTEXT_FILES = 20
MAX_LLM_FILE_CONTEXT_CHARS = 2000


def run_review_svn(
    svn_working_copy: Path,
    agent_dir: Path,
    output_root: Path,
    provider: Optional[BaseLLMProvider] = None,
) -> Path:
    spec = load_agent_spec(agent_dir)
    if spec.get("agent", {}).get("type") != "review-agent":
        raise SystemExit("review-svn requires agent.agent.type == review-agent")

    run_dir = _new_run_dir(output_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    state = new_run_state("review_svn", agent_dir=agent_dir, work_copy=svn_working_copy)
    ensure_approval_log(run_dir)
    _write_json(run_dir / "pending_approvals.json", [])

    permission_checks: List[Dict[str, Any]] = []
    run_log: Dict[str, Any] = {
        "type": "review_svn",
        "agent_dir": str(agent_dir),
        "svn_working_copy": str(svn_working_copy),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "loaded_memory_files": [],
        "provider": getattr(provider, "name", "heuristic") if provider else "heuristic",
        "errors": [],
    }
    context_snapshot: Dict[str, Any] = {"changed_files": [], "loaded_memory_files": [], "file_context": {}}

    try:
        resolutions = resolve_required_capabilities(spec)
        run_log["capability_resolution"] = [item.to_dict() for item in resolutions]
        mark_step(state, "capability_resolution", "completed")
    except CapabilityResolutionError as exc:
        mark_step(state, "capability_resolution", "failed", {"error": str(exc)})
        run_log["errors"].append(str(exc))
        _write_common_outputs(run_dir, spec, [], [], permission_checks, run_log, context_snapshot, state)
        raise SystemExit(str(exc)) from exc

    try:
        root = find_svn_working_copy_root(svn_working_copy)
        run_log["svn_root"] = str(root)
        mark_step(state, "find_svn_root", "completed", {"root": str(root)})
    except SVNToolError as exc:
        mark_step(state, "find_svn_root", "failed", {"error": str(exc)})
        run_log["errors"].append(str(exc))
        _write_common_outputs(run_dir, spec, [], [], permission_checks, run_log, context_snapshot, state)
        raise SystemExit(str(exc)) from exc

    diff_decision = _record_permission(spec, "svn.diff", {"cwd": str(root), "target": str(svn_working_copy)}, permission_checks, run_dir)
    if diff_decision.status != "allowed":
        mark_step(state, "svn_diff", diff_decision.status, {"reason": diff_decision.reason})
        run_log["errors"].append(diff_decision.reason)
        _write_common_outputs(run_dir, spec, [], [], permission_checks, run_log, context_snapshot, state)
        return run_dir

    try:
        diff_text = run_svn_diff(svn_working_copy)
        mark_step(state, "svn_diff", "completed", {"bytes": len(diff_text.encode("utf-8"))})
    except SVNToolError as exc:
        mark_step(state, "svn_diff", "failed", {"error": str(exc)})
        run_log["errors"].append(str(exc))
        _write_common_outputs(run_dir, spec, [], [], permission_checks, run_log, context_snapshot, state)
        raise SystemExit(str(exc)) from exc

    status_decision = _record_permission(spec, "svn.status", {"cwd": str(root), "target": str(svn_working_copy)}, permission_checks, run_dir)
    if status_decision.status == "allowed":
        status_text = _safe_svn_status(svn_working_copy, run_log)
        mark_step(state, "svn_status", "completed", {"bytes": len(status_text.encode("utf-8"))})
    else:
        mark_step(state, "svn_status", status_decision.status, {"reason": status_decision.reason})
        run_log.setdefault("warnings", []).append(status_decision.reason)

    changed_files = parse_changed_files_from_diff(diff_text)
    context_snapshot["changed_files"] = changed_files
    mark_step(state, "parse_diff_files", "completed", {"changed_files": changed_files})

    file_context: Dict[str, str] = {}
    fs_decision = _record_permission(spec, "fs.read", {"changed_files": changed_files}, permission_checks, run_dir)
    if fs_decision.status == "allowed":
        context_files = changed_files[:MAX_CONTEXT_FILES]
        file_context = read_changed_file_context(root, context_files)
        context_snapshot["file_context"] = _context_metadata(root, context_files)
        context_snapshot["file_context_omitted"] = max(0, len(changed_files) - len(context_files))
        mark_step(state, "read_file_context", "completed", {"files": len(file_context), "omitted": context_snapshot["file_context_omitted"]})
    else:
        mark_step(state, "read_file_context", fs_decision.status, {"reason": fs_decision.reason})
        run_log["errors"].append(fs_decision.reason)

    search_decision = _record_permission(spec, "code.search", {"changed_files": changed_files}, permission_checks, run_dir)
    mark_step(state, "code_search_permission", search_decision.status, {"reason": search_decision.reason})

    learned_rules = _load_learned_rules(agent_dir, run_log, context_snapshot)
    run_log["diff"] = {"chars": len(diff_text), "llm_prompt_chars": min(len(diff_text), MAX_LLM_DIFF_CHARS), "truncated_for_llm": len(diff_text) > MAX_LLM_DIFF_CHARS}
    findings, tests, rule_patch, used_llm = _analyze_review(spec, diff_text, file_context, learned_rules, provider, run_log)
    report = _render_runtime_report(spec, findings, used_llm)
    if used_llm and run_log.get("llm_report_markdown"):
        report = str(run_log["llm_report_markdown"])
    _write_analysis_outputs(run_dir, report, findings, tests, rule_patch)
    mark_step(state, "review_analysis", "completed", {"mode": "llm" if used_llm else "heuristic"})

    test_decision = _record_permission(
        spec,
        "shell.run_tests",
        {"reason": "Review runtime suggests tests but does not execute them automatically."},
        permission_checks,
        run_dir,
    )
    mark_step(state, "run_tests_permission", test_decision.status, {"reason": test_decision.reason})

    state["status"] = "completed_with_pending_approvals" if pending_count(run_dir) else "completed"
    _write_common_outputs(run_dir, spec, findings, tests, permission_checks, run_log, context_snapshot, state, overwrite_analysis=False)
    return run_dir


def _new_run_dir(output_root: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = output_root / f"review_svn_{stamp}"
    counter = 1
    while candidate.exists():
        candidate = output_root / f"review_svn_{stamp}_{counter}"
        counter += 1
    return candidate


def _record_permission(
    spec: Dict[str, Any],
    tool: str,
    payload: Dict[str, Any],
    permission_checks: List[Dict[str, Any]],
    run_dir: Path,
) -> PermissionDecision:
    decision = check_permission(spec, tool, payload=payload)
    data = decision.to_dict()
    permission_checks.append(data)
    if decision.status == "requires_approval" and decision.approval_request:
        add_pending_approval(run_dir, decision.approval_request)
    return decision


def _safe_svn_status(root: Path, run_log: Dict[str, Any]) -> str:
    try:
        return run_svn_status(root)
    except SVNToolError as exc:
        run_log.setdefault("warnings", []).append(f"svn status failed: {exc}")
        return ""


def _load_learned_rules(agent_dir: Path, run_log: Dict[str, Any], context_snapshot: Dict[str, Any]) -> str:
    path = agent_dir / "learned_rules.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    item = {"path": str(path), "bytes": len(text.encode("utf-8"))}
    run_log["loaded_memory_files"].append(item)
    context_snapshot["loaded_memory_files"].append(item)
    return text


def _analyze_review(
    spec: Dict[str, Any],
    diff_text: str,
    file_context: Dict[str, str],
    learned_rules: str,
    provider: Optional[BaseLLMProvider],
    run_log: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[str], str, bool]:
    if provider is not None:
        prompt = json.dumps(
            {
                "agent_spec": spec,
                "diff_text": _bounded_diff_for_prompt(diff_text),
                "diff_truncated_for_llm": len(diff_text) > MAX_LLM_DIFF_CHARS,
                "diff_total_chars": len(diff_text),
                "file_context": _bounded_prompt_context(file_context),
                "learned_rules": learned_rules,
            },
            ensure_ascii=False,
            indent=2,
        )
        try:
            result = provider.complete_json(
                system_prompt=REVIEW_SYSTEM_PROMPT,
                user_prompt=prompt,
                schema=REVIEW_DRY_RUN_SCHEMA,
                schema_name="review_dry_run",
                temperature=0.2,
            )
            run_log["llm_report_markdown"] = result.get("report_markdown", "")
            return (
                result.get("findings", []),
                result.get("test_suggestions", []),
                result.get("rule_patch_markdown", "# Rule Patch Proposal\n"),
                True,
            )
        except Exception as exc:
            run_log.setdefault("warnings", []).append(f"LLM review failed, used heuristic fallback: {exc}")
    findings = analyze_diff_heuristically(diff_text)
    if not findings:
        findings = [
            {
                "id": "F001",
                "severity": "low",
                "title": "未发现明确高风险模式",
                "evidence": ["review runtime heuristic did not match known risk patterns"],
                "recommendation": "请结合项目上下文进行人工复核。",
                "confidence": 0.35,
                "feedback_options": ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"],
            }
        ]
    return findings, suggest_tests(findings), propose_rule_patch(findings), False


def _bounded_prompt_context(file_context: Dict[str, str]) -> Dict[str, str]:
    return {
        path: text[:MAX_LLM_FILE_CONTEXT_CHARS]
        for path, text in list(file_context.items())[:MAX_LLM_CONTEXT_FILES]
    }


def _bounded_diff_for_prompt(diff_text: str) -> str:
    if len(diff_text) <= MAX_LLM_DIFF_CHARS:
        return diff_text
    return (
        diff_text[:MAX_LLM_DIFF_CHARS]
        + "\n\n[Agent Foundry note: diff was truncated before sending to LLM. "
        + f"Total chars: {len(diff_text)}.]\n"
    )


def _render_runtime_report(spec: Dict[str, Any], findings: List[Dict[str, Any]], used_llm: bool) -> str:
    report = render_review_report(spec, findings)
    return report.replace("# Dry Run Review Report", "# SVN Review Report", 1) if not used_llm else report


def _write_analysis_outputs(run_dir: Path, report: str, findings: List[Dict[str, Any]], tests: List[str], rule_patch: str) -> None:
    (run_dir / "review_report.md").write_text(report, encoding="utf-8")
    _write_json(run_dir / "findings.json", findings)
    _write_json(run_dir / "feedback_requests.json", batch_feedback_requests(findings))
    (run_dir / "test_suggestions.md").write_text("# Test Suggestions\n\n" + "\n".join(f"- {item}" for item in tests) + "\n", encoding="utf-8")
    (run_dir / "rule_patch_proposal.md").write_text(rule_patch, encoding="utf-8")


def _write_common_outputs(
    run_dir: Path,
    spec: Dict[str, Any],
    findings: List[Dict[str, Any]],
    tests: List[str],
    permission_checks: List[Dict[str, Any]],
    run_log: Dict[str, Any],
    context_snapshot: Dict[str, Any],
    state: Dict[str, Any],
    *,
    overwrite_analysis: bool = True,
) -> None:
    if overwrite_analysis or not (run_dir / "review_report.md").exists():
        _write_analysis_outputs(run_dir, _render_runtime_report(spec, findings, False), findings, tests, "# Rule Patch Proposal\n\n本次运行未生成具体规则补丁。\n")
    run_log["finished_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(run_dir / "run_log.json", run_log)
    _write_json(run_dir / "permission_checks.json", {"type": "permission_checks", "checks": permission_checks})
    _write_json(run_dir / "context_snapshot.json", context_snapshot)
    save_run_state(run_dir, state)
    if not (run_dir / "pending_approvals.json").exists():
        _write_json(run_dir / "pending_approvals.json", [])
    ensure_approval_log(run_dir)


def _context_metadata(root: Path, changed_files: List[str], max_bytes_per_file: int = 20000) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for changed_file in changed_files:
        target = (root / changed_file).resolve()
        if not target.exists() or not target.is_file():
            result[changed_file] = {"bytes": 0, "truncated": False, "missing": True}
            continue
        size = target.stat().st_size
        result[changed_file] = {"bytes": min(size, max_bytes_per_file), "truncated": size > max_bytes_per_file}
    return result


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_approvals(run_dir: Path) -> List[Dict[str, Any]]:
    return load_pending_approvals(run_dir)


def resume_review_run(run_dir: Path) -> Dict[str, Any]:
    approvals = load_pending_approvals(run_dir)
    if not approvals:
        return {"status": "no_pending_approvals", "message": "no pending approvals"}
    pending = [item for item in approvals if item.get("status") == "pending"]
    if pending:
        return {"status": "pending", "pending_approvals": pending}
    return {"status": "resumed", "message": "approval decisions recorded; no completed step was re-run"}


def memory_review(run_dir: Path) -> str:
    path = run_dir / "rule_patch_proposal.md"
    if not path.exists():
        raise SystemExit(f"rule_patch_proposal.md not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"rule_patch_proposal.md is empty: {path}")
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:8])


def memory_apply(agent_dir: Path, run_dir: Path, patch_file: str) -> Path:
    patch_path = run_dir / patch_file
    if not patch_path.exists():
        raise SystemExit(f"memory patch not found: {patch_path}")
    patch_text = patch_path.read_text(encoding="utf-8").strip()
    if not patch_text:
        raise SystemExit(f"memory patch is empty: {patch_path}")
    learned_rules = agent_dir / "learned_rules.md"
    with learned_rules.open("a", encoding="utf-8") as handle:
        handle.write("\n\n## Applied Rule Patch\n\n")
        handle.write(patch_text)
        handle.write("\n")
    entry = {
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "source_run": str(run_dir),
        "patch_file": patch_file,
        "approval_required": True,
        "approved_by_user": True,
    }
    with (agent_dir / "memory_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return learned_rules


def memory_reject(agent_dir: Path, run_dir: Path, patch_file: str, reason: str) -> Path:
    entry = {
        "rejected_at": datetime.now().isoformat(timespec="seconds"),
        "source_run": str(run_dir),
        "reason": reason,
        "patch_file": patch_file,
    }
    target = agent_dir / "rejected_rule_patches.jsonl"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return target
