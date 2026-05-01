from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from agent_foundry.llm.provider import BaseLLMProvider, LLMError
from agent_foundry.llm.schemas import REVIEW_DRY_RUN_SCHEMA, WRITING_DRY_RUN_SCHEMA


REVIEW_SYSTEM = """You are the dry-run brain for a code review Agent.
Given an AgentSpec and a sample diff, simulate what the generated Agent would output.
Be concise, evidence-based, and conservative. Do not claim to have executed tools.
Return only JSON matching the schema.
"""

WRITING_SYSTEM = """You are the dry-run brain for a writing Agent.
Given an AgentSpec and sample material, simulate a first writing workflow output.
Prefer practical, non-marketing, technically grounded writing unless the spec says otherwise.
Return only JSON matching the schema.
"""


def run_llm_review_dry_run(spec: Dict[str, Any], diff_text: str, run_dir: Path, provider: BaseLLMProvider) -> Path:
    payload = {"agent_spec": spec, "sample_diff": diff_text[:12000]}
    try:
        data = provider.complete_json(
            task="review_dry_run",
            system=REVIEW_SYSTEM,
            user=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=REVIEW_DRY_RUN_SCHEMA,
            temperature=0.2,
        )
    except LLMError:
        from .dry_run import run_review_dry_run

        return run_review_dry_run(spec, diff_text, run_dir)
    _write_review_outputs(data, spec, run_dir)
    return run_dir


def run_llm_writing_dry_run(spec: Dict[str, Any], material: str, run_dir: Path, provider: BaseLLMProvider) -> Path:
    payload = {"agent_spec": spec, "sample_material": material[:12000]}
    try:
        data = provider.complete_json(
            task="writing_dry_run",
            system=WRITING_SYSTEM,
            user=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=WRITING_DRY_RUN_SCHEMA,
            temperature=0.4,
        )
    except LLMError:
        from .dry_run import run_writing_dry_run

        return run_writing_dry_run(spec, material, run_dir)
    _write_writing_outputs(data, run_dir)
    return run_dir


def _write_review_outputs(data: Dict[str, Any], spec: Dict[str, Any], run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    findings = []
    for i, finding in enumerate(data.get("findings", []), start=1):
        item = dict(finding)
        item.setdefault("id", f"F{i:03d}")
        item.setdefault("feedback_options", ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"])
        if "feedback_options" not in item:
            item["feedback_options"] = ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"]
        findings.append(item)
    report_lines = [
        f"# LLM Dry Run Review Report: {spec['agent']['name']}",
        "",
        "## Summary",
        "",
        data.get("summary", ""),
        "",
        "## Findings",
        "",
    ]
    for f in findings:
        report_lines.extend(
            [
                f"### {f['id']} [{f.get('severity', 'info')}] {f.get('title', '')}",
                "",
                f"- 置信度：{f.get('confidence', '')}",
                "- 证据：",
            ]
        )
        for evidence in f.get("evidence", []):
            report_lines.append(f"  - `{evidence}`")
        report_lines.extend([
            f"- 建议：{f.get('recommendation', '')}",
            "- 可反馈标签：accepted / false_positive / too_minor / duplicate / needs_more_evidence",
            "",
        ])
    (run_dir / "review_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    tests = data.get("test_suggestions", [])
    (run_dir / "test_suggestions.md").write_text("# Test Suggestions\n\n" + "\n".join(f"- {x}" for x in tests) + "\n", encoding="utf-8")
    patch = data.get("rule_patch_proposal", "")
    (run_dir / "rule_patch_proposal.md").write_text("# Rule Patch Proposal\n\n```diff\n" + patch + "\n```\n\n需用户确认后才能写入 learned_rules.md。\n", encoding="utf-8")


def _write_writing_outputs(data: Dict[str, Any], run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    topics = data.get("topic_options", [])
    outline = data.get("outline", [])
    (run_dir / "topic_options.md").write_text("# Topic Options\n\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(topics, 1)) + "\n", encoding="utf-8")
    (run_dir / "outline.md").write_text("# Outline\n\n" + "\n".join(f"- {x}" for x in outline) + "\n", encoding="utf-8")
    (run_dir / "article.md").write_text(data.get("article", ""), encoding="utf-8")
    (run_dir / "publish_package.json").write_text(json.dumps(data.get("publish_package", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    patch = data.get("style_rule_patch", "")
    (run_dir / "style_rule_patch.md").write_text("# Style Rule Patch Proposal\n\n```diff\n" + patch + "\n```\n\n需用户确认后才能写入 style_rules.md。\n", encoding="utf-8")
