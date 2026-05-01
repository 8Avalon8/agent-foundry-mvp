from __future__ import annotations

from typing import Dict, List


ALLOWED_REVIEW_LABELS = {"accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"}


def propose_memory_patch(feedback_items: List[Dict]) -> str:
    """Create a simple rule patch proposal from labeled feedback.

    This is intentionally conservative: it proposes text, never writes memory directly.
    """
    lines = ["# Rule Patch Proposal", "", "以下内容必须经用户确认后才能写入长期记忆；本文件只是候选补丁，不会自动更新 learned_rules.md。", ""]
    for item in feedback_items:
        label = item.get("label")
        if label not in ALLOWED_REVIEW_LABELS:
            raise ValueError(f"Unsupported review feedback label: {label}")
        reason = item.get("reason", "")
        title = item.get("title", item.get("finding_id", "unknown"))
        if label == "false_positive":
            lines.extend(["```diff", f"+ 对于 `{title}` 类型的 finding，若满足用户说明的上下文：{reason}，则降低置信度或不报告。", "```", ""])
        elif label == "accepted":
            lines.extend(["```diff", f"+ `{title}` 被用户采纳；类似模式后续应优先报告，并要求提供明确证据。", "```", ""])
        elif label == "too_minor":
            lines.extend(["```diff", f"+ `{title}` 被标记为太细微；类似问题默认降级，除非影响正确性、发布风险或维护成本。", "```", ""])
        elif label == "duplicate":
            lines.extend(["```diff", f"+ `{title}` 被标记为重复；合并同类 finding，避免在同一报告中重复打扰用户。", "```", ""])
        elif label == "needs_more_evidence":
            lines.extend(["```diff", f"+ `{title}` 需要更多证据；类似 finding 必须补充文件位置、触发条件或可复现路径后再报告。", "```", ""])
    if len(lines) == 4:
        lines.append("暂无可沉淀规则。\n")
    return "\n".join(lines)


def propose_style_patch(selected_topic: str, feedback: str) -> str:
    lines = [
        "# Style Rule Patch Proposal",
        "",
        "以下内容必须经用户确认后才能写入长期风格记忆；本文件只是候选补丁，不会自动更新 style_rules.md。",
        "",
        "```diff",
        f"+ 用户选择选题方向：{selected_topic}",
    ]
    if feedback:
        lines.append(f"+ 写作反馈应转化为风格约束：{feedback}")
    else:
        lines.append("+ 用户未提供额外风格反馈；暂不新增具体风格规则。")
    lines.extend(["```", ""])
    return "\n".join(lines)
