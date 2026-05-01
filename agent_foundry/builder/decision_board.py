from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AgentDesignCard, DecisionBoard, DecisionQuestion, PreSpecSession
from .intent_parser import parse_intent
from .presets import find_preset, get_presets, get_recommended_preset
from .decision_graph import get_agent_summary, get_questions, get_stage_order, next_stage, required_question_ids
from .impact_preview import build_impact_preview, impact_preview_as_diff


def create_session(user_goal: str, explicit_type: Optional[str] = None) -> PreSpecSession:
    parsed = parse_intent(user_goal, explicit_type=explicit_type)
    session = PreSpecSession(user_goal=user_goal, inferred_agent_type=parsed.likely_agent_type)
    session.metadata["builder_mode"] = "offline"
    session.metadata["parsed_intent"] = parsed.to_dict()
    session.refresh_unresolved(required_question_ids(parsed.likely_agent_type))
    return session


def _session_questions(session: PreSpecSession, stage: str) -> List[DecisionQuestion]:
    questions = list(get_questions(session.inferred_agent_type, stage))
    # LLM dynamic questions are optional. They are stored as normalized
    # DecisionQuestion dictionaries in session.metadata so renderers and the
    # compiler remain deterministic.
    try:
        from .llm_builder import dynamic_questions_for_stage

        questions.extend(dynamic_questions_for_stage(session, stage))
    except Exception:
        pass
    return questions


def _summary_for_session(session: PreSpecSession):
    summary = get_agent_summary(session.inferred_agent_type, session.user_goal)
    design = session.metadata.get("llm_design") or {}
    if design:
        if design.get("title"):
            summary.title = design["title"]
        if design.get("risk_level"):
            summary.risk_level = design["risk_level"]
        if design.get("summary"):
            summary.summary = list(design["summary"])
    return summary


def apply_preset(session: PreSpecSession, preset_id: Optional[str] = None, source: str = "recommended_accepted") -> None:
    preset = find_preset(session.inferred_agent_type, preset_id) if preset_id else get_recommended_preset(session.inferred_agent_type)
    session.selected_preset = preset.id
    for key, value in preset.decisions.items():
        session.apply_decision(key, value, source=source, confidence="medium" if source == "default" else "high")


def apply_recommended_defaults(session: PreSpecSession, include_all_stages: bool = True) -> None:
    stages = get_stage_order(session.inferred_agent_type) if include_all_stages else [session.current_stage]
    for stage in stages:
        for question in _session_questions(session, stage):
            if question.id not in session.decisions:
                default_value = question.recommended if question.recommended is not None else question.default
                if default_value is not None:
                    session.apply_decision(question.id, default_value, source="recommended_accepted", confidence="medium")


def build_decision_board(session: PreSpecSession) -> DecisionBoard:
    summary = _summary_for_session(session)
    impacts = build_impact_preview(session)
    return DecisionBoard(
        session_id=session.id,
        stage=session.current_stage,
        title=f"{summary.title} 设计草案",
        summary=summary,
        presets=get_presets(session.inferred_agent_type),
        questions=_session_questions(session, session.current_stage),
        decisions={k: v.to_dict() for k, v in session.decisions.items()},
        impact_preview=impacts,
    )


def advance_stage(session: PreSpecSession) -> bool:
    nxt = next_stage(session.current_stage)
    if not nxt:
        return False
    session.current_stage = nxt
    return True


def generate_design_card(session: PreSpecSession) -> AgentDesignCard:
    summary = _summary_for_session(session)
    confirmed: List[str] = []
    question_titles: Dict[str, str] = {}
    for stage in get_stage_order(session.inferred_agent_type):
        for q in _session_questions(session, stage):
            question_titles[q.id] = q.title
    for key, decision in session.decisions.items():
        title = question_titles.get(key, key)
        confirmed.append(f"{title}：{decision.value}")
    unresolved = [question_titles.get(key, key) for key in session.unresolved if key not in session.decisions]
    preset_title = session.selected_preset or "未选择 preset"
    recommendation = f"当前采用 `{preset_title}`，可在后续阶段继续细化权限、反馈和记忆策略。"
    llm_design = session.metadata.get("llm_design") or {}
    if llm_design.get("recommended_preset_reason"):
        recommendation += f"\n\nLLM 推荐理由：{llm_design['recommended_preset_reason']}"
    next_step = "确认后可编译 AgentSpec，并生成 Agent 工程文件。"
    return AgentDesignCard(summary.title, confirmed, unresolved, recommendation, next_step)


def save_session(session: PreSpecSession, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_session(path: Path) -> PreSpecSession:
    return PreSpecSession.from_dict(json.loads(path.read_text(encoding="utf-8")))


def render_board_markdown(board: DecisionBoard) -> str:
    data = board.to_dict()
    lines: List[str] = []
    lines.append(f"# {data['title']}")
    lines.append("")
    lines.append(f"阶段：`{data['stage']}`")
    lines.append(f"类型：`{data['summary']['agent_type']}` | 风险：`{data['summary']['risk_level']}`")
    lines.append("")
    lines.append("## 目标理解")
    for item in data["summary"]["summary"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 推荐组合")
    for preset in data["presets"]:
        rec = "  **推荐**" if preset.get("recommended") else ""
        lines.append(f"### {preset['id']}: {preset['title']}{rec}")
        lines.append(preset["description"])
        for s in preset.get("summary", []):
            lines.append(f"- {s}")
        lines.append("")
    lines.append("## 当前阶段问题")
    for idx, q in enumerate(data["questions"], start=1):
        lines.append(f"### {idx}. {q['title']}")
        lines.append(f"类型：`{q['input_type']}` | 推荐：`{q.get('recommended')}` | 风险：`{q.get('risk_level')}`")
        if q.get("recommendation_reason"):
            lines.append(f"推荐原因：{q['recommendation_reason']}")
        for opt in q.get("options", []):
            rec = " [推荐]" if opt.get("recommended") or opt.get("id") == q.get("recommended") else ""
            if isinstance(q.get("recommended"), list) and opt.get("id") in q.get("recommended"):
                rec = " [推荐]"
            tradeoff = f" — {opt.get('tradeoff')}" if opt.get("tradeoff") else ""
            lines.append(f"- `{opt['id']}` {opt['label']}{rec}{tradeoff}")
        if q.get("affects"):
            lines.append("影响：" + ", ".join(q["affects"]))
        lines.append("")
    lines.append("## Impact Preview")
    lines.append("```text")
    lines.append(impact_preview_as_diff(board.impact_preview))
    lines.append("```")
    return "\n".join(lines)


def render_board_cli(board: DecisionBoard) -> str:
    data = board.to_dict()
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append(f"{data['title']}")
    lines.append(f"阶段：{data['stage']} | 类型：{data['summary']['agent_type']} | 风险：{data['summary']['risk_level']}")
    lines.append("-" * 72)
    lines.append("目标理解：")
    for item in data["summary"]["summary"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("推荐组合：")
    for preset in data["presets"]:
        rec = " [推荐]" if preset.get("recommended") else ""
        lines.append(f"  {preset['id']}: {preset['title']}{rec}")
        lines.append(f"    {preset['description']}")
    lines.append("")
    lines.append("需要确认：")
    for idx, q in enumerate(data["questions"], start=1):
        lines.append(f"\n{idx}. {q['title']}")
        lines.append(f"   推荐：{q.get('recommended')}")
        if q.get("recommendation_reason"):
            lines.append(f"   原因：{q['recommendation_reason']}")
        for opt in q.get("options", []):
            rec = ""
            if opt.get("recommended") or opt.get("id") == q.get("recommended"):
                rec = " [推荐]"
            if isinstance(q.get("recommended"), list) and opt.get("id") in q.get("recommended"):
                rec = " [推荐]"
            lines.append(f"   - {opt['id']}: {opt['label']}{rec}")
            if opt.get("tradeoff"):
                lines.append(f"     取舍：{opt['tradeoff']}")
            if opt.get("requires_input"):
                lines.append(f"     需要补充：{opt['requires_input'].get('placeholder', '')}")
    if data.get("impact_preview"):
        lines.append("\nImpact Preview:")
        for item in data["impact_preview"]:
            lines.append(f"  + {item['path']} = {item['value']}  # {item.get('reason', '')}")
    lines.append("=" * 72)
    return "\n".join(lines)


def render_board_html(board: DecisionBoard) -> str:
    data = board.to_dict()
    json_payload = json.dumps(data, ensure_ascii=False, indent=2)

    def esc(s: Any) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    preset_cards = []
    for p in data["presets"]:
        badge = '<span class="badge recommended">推荐</span>' if p.get("recommended") else ""
        summary = "".join(f"<li>{esc(x)}</li>" for x in p.get("summary", []))
        preset_cards.append(
            f"""
        <article class="preset-card {'selected' if p.get('recommended') else ''}">
          <div class="card-head"><h3>{esc(p['title'])}</h3>{badge}</div>
          <p>{esc(p['description'])}</p>
          <ul>{summary}</ul>
        </article>
        """
        )

    question_cards = []
    for q in data["questions"]:
        options_html = []
        input_type = "checkbox" if q["input_type"] == "multi_choice" else "radio"
        name = esc(q["id"])
        recommended = q.get("recommended")
        for opt in q.get("options", []):
            checked = False
            if isinstance(recommended, list):
                checked = opt["id"] in recommended
            else:
                checked = opt["id"] == recommended or opt.get("recommended", False)
            extra = ""
            if opt.get("requires_input"):
                extra = f"<input class='inline-input' placeholder='{esc(opt['requires_input'].get('placeholder',''))}' />"
            tradeoff = f"<small>{esc(opt.get('tradeoff',''))}</small>" if opt.get("tradeoff") else ""
            options_html.append(
                f"""
            <label class="option-row">
              <input type="{input_type}" name="{name}" value="{esc(opt['id'])}" {'checked' if checked else ''}>
              <span>{esc(opt['label'])}</span>
              {'<b>推荐</b>' if checked else ''}
              {tradeoff}
              {extra}
            </label>
            """
            )
        affects = "".join(f"<code>{esc(a)}</code>" for a in q.get("affects", []))
        question_cards.append(
            f"""
        <section class="decision-card">
          <div class="card-head">
            <h3>{esc(q['title'])}</h3>
            <span class="badge risk">{esc(q.get('risk_level',''))}</span>
          </div>
          <p class="reason"><strong>推荐：</strong>{esc(q.get('recommended'))}<br>{esc(q.get('recommendation_reason',''))}</p>
          <div class="options">{''.join(options_html)}</div>
          <div class="affects">影响：{affects}</div>
        </section>
        """
        )

    impact = "\n".join(f"+ {esc(i['path'])}: {esc(i['value'])}" for i in data.get("impact_preview", []))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{esc(data['title'])}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f6f7fb; color: #1f2937; }}
  main {{ max-width: 1120px; margin: 0 auto; padding: 32px; }}
  header, .panel {{ background: white; border: 1px solid #e5e7eb; border-radius: 18px; padding: 24px; box-shadow: 0 10px 30px rgba(15,23,42,.06); margin-bottom: 20px; }}
  h1 {{ margin: 0 0 8px; font-size: 28px; }}
  .muted {{ color: #6b7280; }}
  .preset-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
  .preset-card, .decision-card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px; }}
  .preset-card.selected {{ border-color: #111827; }}
  .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
  .badge {{ border-radius: 999px; padding: 3px 9px; font-size: 12px; background: #eef2ff; }}
  .recommended {{ background: #dcfce7; }}
  .risk {{ background: #fef3c7; }}
  .decision-card {{ margin: 14px 0; }}
  .option-row {{ display: grid; grid-template-columns: 24px 1fr auto; gap: 8px; align-items: start; padding: 10px; border-radius: 10px; background: #f9fafb; margin: 8px 0; }}
  .option-row small {{ grid-column: 2 / span 2; color: #6b7280; }}
  .inline-input {{ grid-column: 2 / span 2; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }}
  code, pre {{ background: #111827; color: #e5e7eb; border-radius: 10px; padding: 2px 6px; }}
  pre {{ padding: 14px; overflow: auto; }}
  details pre {{ white-space: pre-wrap; }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{esc(data['title'])}</h1>
    <div class="muted">阶段：{esc(data['stage'])} | 类型：{esc(data['summary']['agent_type'])} | 风险：{esc(data['summary']['risk_level'])}</div>
    <ul>{''.join(f'<li>{esc(x)}</li>' for x in data['summary']['summary'])}</ul>
  </header>
  <section class="panel"><h2>推荐组合</h2><div class="preset-grid">{''.join(preset_cards)}</div></section>
  <section class="panel"><h2>需要确认</h2>{''.join(question_cards)}</section>
  <section class="panel"><h2>Impact Preview</h2><pre>{impact or '# 暂无影响预览'}</pre></section>
  <details class="panel"><summary>完整 DecisionBoard JSON</summary><pre>{esc(json_payload)}</pre></details>
</main>
</body>
</html>"""

