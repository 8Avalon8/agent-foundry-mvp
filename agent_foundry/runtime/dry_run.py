from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .feedback_engine import batch_feedback_requests, topic_selection_request
from .permission_engine import permission_checks_for_spec


def load_agent_spec(agent_dir: Path) -> Dict[str, Any]:
    agent_file = agent_dir / "agent.yaml"
    if not agent_file.exists():
        raise FileNotFoundError(f"agent.yaml not found: {agent_file}")
    return yaml.safe_load(agent_file.read_text(encoding="utf-8"))


def dry_run(
    agent_dir: Path,
    sample_input: Path | None = None,
    output_dir: Path | None = None,
    provider: Optional[Any] = None,
) -> Path:
    spec = load_agent_spec(agent_dir)
    agent_type = spec["agent"]["type"]
    run_dir = output_dir or agent_dir / "runs" / f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "permission_checks.json").write_text(
        json.dumps(permission_checks_for_spec(spec), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if agent_type == "review-agent":
        if sample_input is None:
            sample_input = agent_dir / "examples" / "sample_input.diff"
        diff_text = sample_input.read_text(encoding="utf-8")
        if provider is not None:
            try:
                return run_review_dry_run_llm(spec, diff_text, run_dir, provider)
            except Exception as exc:
                (run_dir / "llm_fallback_note.md").write_text(
                    f"# LLM Dry Run Fallback\n\nLLM dry run failed, used heuristic fallback.\n\n```text\n{exc}\n```\n",
                    encoding="utf-8",
                )
        return run_review_dry_run(spec, diff_text, run_dir)
    if agent_type == "writing-agent":
        if sample_input is None:
            sample_input = agent_dir / "examples" / "sample_material.txt"
        material = sample_input.read_text(encoding="utf-8")
        if provider is not None:
            try:
                return run_writing_dry_run_llm(spec, material, run_dir, provider)
            except Exception as exc:
                (run_dir / "llm_fallback_note.md").write_text(
                    f"# LLM Dry Run Fallback\n\nLLM dry run failed, used deterministic fallback.\n\n```text\n{exc}\n```\n",
                    encoding="utf-8",
                )
        return run_writing_dry_run(spec, material, run_dir)
    if agent_type == "research-agent":
        if sample_input is None:
            sample_input = agent_dir / "examples" / "sample_input.txt"
        request = sample_input.read_text(encoding="utf-8")
        if provider is not None:
            try:
                return run_research_dry_run_llm(spec, request, run_dir, provider)
            except Exception as exc:
                (run_dir / "llm_fallback_note.md").write_text(
                    f"# LLM Dry Run Fallback\n\nLLM dry run failed, used deterministic fallback.\n\n```text\n{exc}\n```\n",
                    encoding="utf-8",
                )
        return run_research_dry_run(spec, request, run_dir)
    (run_dir / "result.md").write_text("# Dry Run\n\nGeneric agent dry run is not implemented yet.\n", encoding="utf-8")
    return run_dir



REVIEW_DRY_RUN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["report_markdown", "findings", "test_suggestions", "rule_patch_markdown"],
    "properties": {
        "report_markdown": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "severity", "title", "evidence", "recommendation", "confidence", "feedback_options"],
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string"},
                    "title": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {"type": "string"},
                    "confidence": {"type": "number"},
                    "feedback_options": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "test_suggestions": {"type": "array", "items": {"type": "string"}},
        "rule_patch_markdown": {"type": "string"},
    },
}


WRITING_DRY_RUN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["topic_options", "outline", "article_markdown", "publish_package", "style_rule_patch_markdown"],
    "properties": {
        "topic_options": {"type": "array", "items": {"type": "string"}},
        "outline": {"type": "array", "items": {"type": "string"}},
        "article_markdown": {"type": "string"},
        "publish_package": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "cover_prompt", "checklist"],
            "properties": {
                "summary": {"type": "string"},
                "cover_prompt": {"type": "string"},
                "checklist": {"type": "array", "items": {"type": "string"}},
            },
        },
        "style_rule_patch_markdown": {"type": "string"},
    },
}


RESEARCH_DRY_RUN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["report_markdown", "research_plan", "sources", "feedback_requests"],
    "properties": {
        "report_markdown": {"type": "string"},
        "research_plan": {"type": "array", "items": {"type": "string"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_url", "source_title", "retrieved_at", "evidence_snippet", "source_type", "confidence", "inference_note"],
                "properties": {
                    "source_url": {"type": "string"},
                    "source_title": {"type": "string"},
                    "retrieved_at": {"type": "string"},
                    "evidence_snippet": {"type": "string"},
                    "source_type": {"type": "string"},
                    "confidence": {"type": "number"},
                    "inference_note": {"type": "string"},
                },
            },
        },
        "feedback_requests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "question", "options"],
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


LLM_DRY_RUN_SYSTEM = """你是 Agent Foundry 的 dry-run 执行器。你会根据 AgentSpec 和示例输入，生成一次模拟运行结果。\n\n要求：\n- 只输出符合 JSON Schema 的对象。\n- 不能执行真实工具、shell、网络或发布动作。\n- 必须体现 AgentSpec 里的权限、人类反馈和记忆更新策略。\n- Review finding 必须包含证据、建议、置信度和反馈标签。\n- Research 报告必须保留 source_url、source_title、retrieved_at、evidence_snippet、source_type、confidence 和 inference_note。\n- Rule Patch / Style Patch 只能是候选，必须标注需要用户审批。\n"""


def run_review_dry_run_llm(spec: Dict[str, Any], diff_text: str, run_dir: Path, provider: Any) -> Path:
    prompt = json.dumps({"agent_spec": spec, "diff_text": diff_text}, ensure_ascii=False, indent=2)
    result = provider.complete_json(
        system_prompt=LLM_DRY_RUN_SYSTEM,
        user_prompt=prompt,
        schema=REVIEW_DRY_RUN_SCHEMA,
        schema_name="review_dry_run",
        temperature=0.2,
    )
    findings = result.get("findings", [])
    (run_dir / "review_report.md").write_text(result.get("report_markdown", "# Review Report\n"), encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "feedback_requests.json").write_text(
        json.dumps(batch_feedback_requests(findings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "test_suggestions.md").write_text(
        "# Test Suggestions\n\n" + "\n".join(f"- {x}" for x in result.get("test_suggestions", [])) + "\n",
        encoding="utf-8",
    )
    (run_dir / "rule_patch_proposal.md").write_text(result.get("rule_patch_markdown", "# Rule Patch Proposal\n"), encoding="utf-8")
    (run_dir / "llm_dry_run_metadata.json").write_text(
        json.dumps({"provider": getattr(provider, "name", "unknown"), "mode": "llm"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def run_writing_dry_run_llm(spec: Dict[str, Any], material: str, run_dir: Path, provider: Any) -> Path:
    prompt = json.dumps({"agent_spec": spec, "material": material}, ensure_ascii=False, indent=2)
    result = provider.complete_json(
        system_prompt=LLM_DRY_RUN_SYSTEM,
        user_prompt=prompt,
        schema=WRITING_DRY_RUN_SCHEMA,
        schema_name="writing_dry_run",
        temperature=0.3,
    )
    package = result.get("publish_package", {})
    topics = result.get("topic_options", [])
    (run_dir / "topic_options.md").write_text(
        "# Topic Options\n\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(topics, 1)) + "\n",
        encoding="utf-8",
    )
    (run_dir / "topic_options.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "topic_selection_request.json").write_text(
        json.dumps(topic_selection_request(topics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "outline.md").write_text("# Outline\n\n" + "\n".join(f"- {x}" for x in result.get("outline", [])) + "\n", encoding="utf-8")
    (run_dir / "article.md").write_text(result.get("article_markdown", "# Article\n"), encoding="utf-8")
    (run_dir / "publish_package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "summary.md").write_text("# Summary\n\n" + str(package.get("summary", "")) + "\n", encoding="utf-8")
    (run_dir / "cover_prompt.md").write_text("# Cover Prompt\n\n" + str(package.get("cover_prompt", "")) + "\n", encoding="utf-8")
    (run_dir / "publish_checklist.md").write_text(
        "# Publish Checklist\n\n" + "\n".join(f"- {x}" for x in package.get("checklist", [])) + "\n",
        encoding="utf-8",
    )
    (run_dir / "style_rule_patch.md").write_text(result.get("style_rule_patch_markdown", "# Style Rule Patch Proposal\n"), encoding="utf-8")
    (run_dir / "llm_dry_run_metadata.json").write_text(
        json.dumps({"provider": getattr(provider, "name", "unknown"), "mode": "llm"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def run_research_dry_run_llm(spec: Dict[str, Any], request: str, run_dir: Path, provider: Any) -> Path:
    prompt = json.dumps({"agent_spec": spec, "research_request": request}, ensure_ascii=False, indent=2)
    result = provider.complete_json(
        system_prompt=LLM_DRY_RUN_SYSTEM,
        user_prompt=prompt,
        schema=RESEARCH_DRY_RUN_SCHEMA,
        schema_name="research_dry_run",
        temperature=0.2,
    )
    sources = result.get("sources", [])
    plan = result.get("research_plan", [])
    feedback = result.get("feedback_requests", [])
    (run_dir / "report.md").write_text(result.get("report_markdown", "# Research Report\n"), encoding="utf-8")
    (run_dir / "research_plan.md").write_text("# Research Plan\n\n" + "\n".join(f"- {x}" for x in plan) + "\n", encoding="utf-8")
    (run_dir / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "feedback_requests.json").write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8")
    if "evidence_matrix.json" in spec.get("output", {}).get("artifacts", []):
        (run_dir / "evidence_matrix.json").write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "llm_dry_run_metadata.json").write_text(
        json.dumps({"provider": getattr(provider, "name", "unknown"), "mode": "llm"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def run_review_dry_run(spec: Dict[str, Any], diff_text: str, run_dir: Path) -> Path:
    findings = analyze_diff_heuristically(diff_text)
    if not findings:
        findings.append(
            {
                "id": "F001",
                "severity": "low",
                "title": "未发现明确高风险模式",
                "evidence": ["dry-run heuristic did not match known risk patterns"],
                "recommendation": "请结合项目上下文进行人工复核。",
                "confidence": 0.35,
                "feedback_options": ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"],
            }
        )
    report = render_review_report(spec, findings)
    tests = suggest_tests(findings)
    rule_patch = propose_rule_patch(findings)

    (run_dir / "review_report.md").write_text(report, encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "feedback_requests.json").write_text(
        json.dumps(batch_feedback_requests(findings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "test_suggestions.md").write_text("# Test Suggestions\n\n" + "\n".join(f"- {x}" for x in tests) + "\n", encoding="utf-8")
    (run_dir / "rule_patch_proposal.md").write_text(rule_patch, encoding="utf-8")
    return run_dir


def analyze_diff_heuristically(diff_text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    lines = diff_text.splitlines()
    removed_null_checks = []
    removed_null_vars = []
    removed_validation = []
    added_direct_calls = []
    added_empty_catch = []
    added_sql_concat = []

    for idx, line in enumerate(lines, start=1):
        content = line[1:] if line.startswith(("+", "-")) else line
        if line.startswith("-") and re.search(r"\bnull\b|isEmpty\(|isBlank\(", content):
            removed_null_checks.append((idx, line))
            m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:==|!=)\s*null", content)
            if m:
                removed_null_vars.append(m.group(1))
        if line.startswith("-") and re.search(r"\bvalidate\s*\(|checkArgument\s*\(|requireNonNull\s*\(", content):
            removed_validation.append((idx, line))
        if not line.startswith("-") and re.search(r"\w+\.\w+\(", content) and "//" not in content:
            # Include unchanged context lines too; removing a guard while leaving a direct call is still risky.
            if removed_null_vars:
                if any(re.search(rf"\b{re.escape(var)}\.", content) for var in removed_null_vars):
                    added_direct_calls.append((idx, line))
            else:
                added_direct_calls.append((idx, line))
        if line.startswith("+") and re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", content):
            added_empty_catch.append((idx, line))
        if line.startswith("+") and re.search(r"select .*\+|where .*\+|executeQuery\(.*\+", content, re.I):
            added_sql_concat.append((idx, line))

    fid = 1
    if removed_null_checks and added_direct_calls:
        findings.append(_finding(fid, "high", "移除了空值/边界保护，但新增或保留了直接对象调用", removed_null_checks[:3] + added_direct_calls[:3], "恢复空值/边界保护，或补充上游非空保证的可验证证据。", 0.78)); fid += 1
    if removed_validation:
        findings.append(_finding(fid, "medium", "移除了输入校验逻辑", removed_validation[:4], "确认该校验是否已迁移到上游；如果没有，应恢复校验或补充测试覆盖非法输入。", 0.72)); fid += 1
    if added_empty_catch:
        findings.append(_finding(fid, "medium", "新增空 catch，可能吞掉异常", added_empty_catch[:4], "至少记录日志或重新抛出；如有意忽略，请说明业务原因。", 0.82)); fid += 1
    if added_sql_concat:
        findings.append(_finding(fid, "high", "疑似 SQL 字符串拼接风险", added_sql_concat[:4], "使用参数化查询或 ORM 参数绑定，避免注入风险。", 0.80)); fid += 1

    # Low-noise maintainability hints.
    for idx, line in enumerate(lines, start=1):
        if line.startswith("+") and "System.out.println" in line:
            findings.append(_finding(fid, "low", "新增控制台输出", [(idx, line)], "使用项目日志框架，并确认不会泄漏敏感信息。", 0.66)); fid += 1
            break
    return findings


def _finding(fid: int, severity: str, title: str, evidence_pairs, recommendation: str, confidence: float) -> Dict[str, Any]:
    return {
        "id": f"F{fid:03d}",
        "severity": severity,
        "title": title,
        "evidence": [f"diff line {line_no}: {text}" for line_no, text in evidence_pairs],
        "recommendation": recommendation,
        "confidence": confidence,
        "feedback_options": ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"],
    }


def render_review_report(spec: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    low = sum(1 for f in findings if f["severity"] == "low")
    lines = [
        f"# Dry Run Review Report: {spec['agent']['name']}",
        "",
        "## Summary",
        "",
        f"本次 dry run 发现 {len(findings)} 条问题：高风险 {high}，中风险 {medium}，低风险 {low}。",
        "",
        "## Findings",
        "",
    ]
    for f in findings:
        lines.extend([
            f"### {f['id']} [{f['severity']}] {f['title']}",
            "",
            f"- 置信度：{f['confidence']}",
            "- 证据：",
        ])
        for e in f["evidence"]:
            lines.append(f"  - `{e}`")
        lines.extend([
            f"- 建议：{f['recommendation']}",
            f"- 可反馈标签：{', '.join(f['feedback_options'])}",
            "",
        ])
    lines.extend([
        "## Feedback Contract",
        "",
        "对每条 finding 可标记：`accepted` / `false_positive` / `too_minor` / `duplicate` / `needs_more_evidence`。",
    ])
    return "\n".join(lines) + "\n"


def suggest_tests(findings: List[Dict[str, Any]]) -> List[str]:
    suggestions = []
    titles = "\n".join(f["title"] for f in findings)
    if "空值" in titles or "边界" in titles:
        suggestions.append("补充空输入 / null 输入的单元测试，验证不会产生 NullPointerException。")
    if "校验" in titles:
        suggestions.append("补充非法请求、缺失字段、边界字段的测试，确认不会绕过校验落库。")
    if "SQL" in titles:
        suggestions.append("补充恶意输入字符串测试，验证使用参数化查询。")
    if not suggestions:
        suggestions.append("补充与本次 diff 涉及分支直接相关的回归测试。")
    return suggestions


def propose_rule_patch(findings: List[Dict[str, Any]]) -> str:
    lines = ["# Rule Patch Proposal", "", "以下规则只是候选，必须由用户确认后才能写入 learned_rules.md。", ""]
    if any("空值" in f["title"] or "边界" in f["title"] for f in findings):
        lines.extend([
            "```diff",
            "+ 当 diff 移除 null / 边界保护，同时仍存在直接对象调用时，默认报告为高风险，除非有明确上游保证。",
            "```",
            "",
        ])
    if any("校验" in f["title"] for f in findings):
        lines.extend([
            "```diff",
            "+ 当 diff 移除 validate / check / requireNonNull 等输入校验时，要求提供上游迁移证据或补充非法输入测试。",
            "```",
            "",
        ])
    if len(lines) <= 4:
        lines.append("本次 dry run 暂未生成具体规则补丁。\n")
    return "\n".join(lines)


def run_research_dry_run(spec: Dict[str, Any], request: str, run_dir: Path) -> Path:
    request = request.strip() or spec.get("goal", {}).get("primary", "研究请求")
    targets = _infer_research_targets(request)
    plan = [
        "确认比较对象和研究维度。",
        "优先读取官方公开页面、价格页和帮助文档。",
        "为每条结论记录来源字段和证据片段。",
        "遇到登录墙、验证码、付费墙或访问限制时停止并标注。",
        "输出对比报告和结构化来源清单。",
    ]
    sources = [
        {
            "source_url": f"https://example.com/{_slug_for_source(target)}",
            "source_title": f"{target} official public page placeholder",
            "retrieved_at": datetime.now().strftime("%Y-%m-%d"),
            "evidence_snippet": f"Dry run placeholder for public evidence about {target}.",
            "source_type": "official_public_page_placeholder",
            "confidence": 0.4,
            "inference_note": "Deterministic dry run did not access the network; replace with real public sources during execution.",
        }
        for target in targets
    ]
    feedback = [
        {
            "id": "RQ001",
            "question": "这些来源字段是否足够支撑你复核报告？",
            "options": ["accepted", "needs_more_evidence", "weak_source", "irrelevant"],
        },
        {
            "id": "RQ002",
            "question": "比较维度是否覆盖你的研究目标？",
            "options": ["accepted", "missing_dimension", "too_broad", "too_shallow"],
        },
    ]
    report = render_research_report(spec, request, targets, sources)
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    (run_dir / "research_plan.md").write_text("# Research Plan\n\n" + "\n".join(f"- {x}" for x in plan) + "\n", encoding="utf-8")
    (run_dir / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "feedback_requests.json").write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8")
    if "evidence_matrix.json" in spec.get("output", {}).get("artifacts", []):
        (run_dir / "evidence_matrix.json").write_text(json.dumps({"sources": sources}, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def render_research_report(spec: Dict[str, Any], request: str, targets: List[str], sources: List[Dict[str, Any]]) -> str:
    lines = [
        f"# Dry Run Research Report: {spec['agent']['name']}",
        "",
        "## Request",
        "",
        request,
        "",
        "## Scope",
        "",
        "- 本次 dry run 不访问真实网络，只验证研究流程、输出结构和权限边界。",
        "- 真实运行时只读取公开页面；登录、验证码、提交表单和外部发布均不会自动执行。",
        "",
        "## Comparison Draft",
        "",
        "| Product | Positioning | Target Users | Core Functions | Pricing Entry | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for target, source in zip(targets, sources):
        lines.append(
            f"| {target} | 待从官方公开页面提取 | 待从官方文案谨慎推断 | 待从产品页和帮助文档提取 | 待记录价格入口 URL | {source['source_url']} |"
        )
    lines.extend(
        [
            "",
            "## Source Contract",
            "",
            "每条事实结论都必须能回到 `sources.json` 中的来源字段：`source_url`、`source_title`、`retrieved_at`、`evidence_snippet`、`source_type`、`confidence`、`inference_note`。",
            "",
            "## Open Questions",
            "",
            "- 是否只接受官方来源，还是允许第三方评测补充？",
            "- 价格信息是只记录入口，还是需要人工确认后整理具体套餐？",
        ]
    )
    return "\n".join(lines) + "\n"


def _infer_research_targets(request: str) -> List[str]:
    candidates = re.split(r"[、,，/和与\s]+", request)
    targets = []
    for item in candidates:
        cleaned = item.strip("：:；;。,. ")
        if cleaned and re.search(r"[A-Za-z]", cleaned) and cleaned.lower() not in {"agent", "url"}:
            targets.append(cleaned)
    return targets[:5] or ["Target A", "Target B", "Target C"]


def _slug_for_source(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"


def run_writing_dry_run(spec: Dict[str, Any], material: str, run_dir: Path) -> Path:
    material = material.strip() or "今天发现 AI 做 code review 最有价值的不是找 bug，而是逼我显式化规则。"
    topics = [
        "AI Review 真正有价值的地方：逼我显式化规则",
        "我开始把 AI 当成 Code Reviewer，而不是搜索引擎",
        "程序员如何训练一个越来越懂项目的 AI 助手",
        "从一次代码审查看 AI 工作流的进化方式",
    ]
    outline = [
        "开头：用一个真实场景说明为什么想到这个问题",
        "第一部分：AI Review 不只是找 bug，而是暴露隐性规则",
        "第二部分：如何把一次反馈沉淀成下一次更好的审查",
        "第三部分：受控半自动比全自动更适合早期落地",
        "结尾：把 AI 当成可训练的工作流，而不是一次性工具",
    ]
    draft = f"""# {topics[0]}

最近我在思考一个问题：{material}

很多人第一次用 AI 做代码审查时，会期待它像一个更快的静态检查器，直接帮我们找 bug。但我越来越觉得，AI Review 更有价值的地方不只是指出某一行代码可能有问题，而是把我们平时说不清楚的工程规则逼出来。

比如，当它误报一次空指针风险时，我需要告诉它：这个对象在上游工厂方法之后一定非空。这个反馈如果只停留在对话里，下一次还会重复发生；但如果它被整理成项目规则，Agent 就会真正进化。
"""
    publish_package = {
        "title_options": topics,
        "summary": "一篇关于 AI Review、规则显式化和 Agent 进化机制的工程实践文章。",
        "cover_prompt": "A clean technical illustration of an AI code reviewer turning vague engineering habits into explicit rules, modern minimal style.",
        "checklist": ["标题不过度营销", "包含真实实践场景", "说明可复用方法", "发布前人工确认"],
    }
    style_patch = """# Style Rule Patch Proposal

```diff
+ 写 AI 工程实践文章时，优先使用真实工作流例子，再上升到方法论。
+ 标题避免“震惊”“彻底改变”等强营销词，保持技术克制感。
```

以上规则需用户确认后写入 style_rules.md。
"""

    (run_dir / "topic_options.md").write_text("# Topic Options\n\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(topics, 1)) + "\n", encoding="utf-8")
    (run_dir / "topic_options.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "topic_selection_request.json").write_text(
        json.dumps(topic_selection_request(topics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "outline.md").write_text("# Outline\n\n" + "\n".join(f"- {x}" for x in outline) + "\n", encoding="utf-8")
    (run_dir / "article.md").write_text(draft, encoding="utf-8")
    (run_dir / "publish_package.json").write_text(json.dumps(publish_package, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "style_rule_patch.md").write_text(style_patch, encoding="utf-8")
    return run_dir
