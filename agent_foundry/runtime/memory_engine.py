from __future__ import annotations

from typing import Dict, List


def propose_memory_patch(feedback_items: List[Dict]) -> str:
    """Create a simple rule patch proposal from labeled feedback.

    This is intentionally conservative: it proposes text, never writes memory directly.
    """
    lines = ["# Memory Patch Proposal", "", "以下内容必须经用户确认后才能写入长期记忆。", ""]
    for item in feedback_items:
        label = item.get("label")
        reason = item.get("reason", "")
        title = item.get("title", item.get("finding_id", "unknown"))
        if label == "false_positive":
            lines.extend(["```diff", f"+ 对于 `{title}` 类型的 finding，若满足用户说明的上下文：{reason}，则降低置信度或不报告。", "```", ""])
        elif label == "accepted":
            lines.extend(["```diff", f"+ `{title}` 被用户采纳；类似模式后续应优先报告，并要求提供明确证据。", "```", ""])
    if len(lines) == 4:
        lines.append("暂无可沉淀规则。\n")
    return "\n".join(lines)
