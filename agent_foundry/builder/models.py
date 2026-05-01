from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


JSONDict = Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class DecisionOption:
    id: str
    label: str
    description: str = ""
    recommended: bool = False
    tradeoff: str = ""
    requires_input: Optional[JSONDict] = None
    risk_level: str = ""

    def to_dict(self) -> JSONDict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: JSONDict) -> "DecisionOption":
        return cls(
            id=str(data.get("id", "option")),
            label=str(data.get("label", data.get("id", "option"))),
            description=str(data.get("description", "")),
            recommended=bool(data.get("recommended", False)),
            tradeoff=str(data.get("tradeoff", "")),
            requires_input=data.get("requires_input"),
            risk_level=str(data.get("risk_level", "")),
        )


@dataclass
class DecisionQuestion:
    id: str
    title: str
    input_type: str
    stage: str
    required: bool = True
    recommended: Optional[Any] = None
    recommendation_reason: str = ""
    risk_level: str = "low"
    options: List[DecisionOption] = field(default_factory=list)
    affects: List[str] = field(default_factory=list)
    help_text: str = ""
    visible_when: Optional[JSONDict] = None
    default: Optional[Any] = None
    placeholder: str = ""

    def to_dict(self) -> JSONDict:
        data = asdict(self)
        data["options"] = [o.to_dict() for o in self.options]
        return data

    @classmethod
    def from_dict(cls, data: JSONDict) -> "DecisionQuestion":
        options = [DecisionOption.from_dict(o) for o in data.get("options", [])]
        return cls(
            id=str(data.get("id", "question")),
            title=str(data.get("title", data.get("id", "question"))),
            input_type=str(data.get("input_type", data.get("type", "single_choice"))),
            stage=str(data.get("stage", "foundation")),
            required=bool(data.get("required", True)),
            recommended=data.get("recommended"),
            recommendation_reason=str(data.get("recommendation_reason", "")),
            risk_level=str(data.get("risk_level", "low")),
            options=options,
            affects=list(data.get("affects", [])),
            help_text=str(data.get("help_text", "")),
            visible_when=data.get("visible_when"),
            default=data.get("default"),
            placeholder=str(data.get("placeholder", "")),
        )


@dataclass
class DecisionStage:
    id: str
    title: str
    description: str
    questions: List[DecisionQuestion] = field(default_factory=list)
    unlock_when: Optional[JSONDict] = None

    def to_dict(self) -> JSONDict:
        data = asdict(self)
        data["questions"] = [q.to_dict() for q in self.questions]
        return data


@dataclass
class PresetProfile:
    id: str
    title: str
    description: str
    recommended: bool = False
    summary: List[str] = field(default_factory=list)
    decisions: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"

    def to_dict(self) -> JSONDict:
        return asdict(self)


@dataclass
class DecisionValue:
    value: Any
    source: str = "user_selected"  # user_selected | recommended_accepted | default | inferred
    confidence: str = "high"
    note: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> JSONDict:
        return asdict(self)


@dataclass
class ImpactItem:
    path: str
    value: Any
    reason: str = ""
    risk_level: str = "low"

    def to_dict(self) -> JSONDict:
        return asdict(self)


@dataclass
class AgentSummary:
    title: str
    agent_type: str
    risk_level: str
    summary: List[str]

    def to_dict(self) -> JSONDict:
        return asdict(self)


@dataclass
class PreSpecSession:
    user_goal: str
    inferred_agent_type: str
    id: str = field(default_factory=lambda: new_id("session"))
    current_stage: str = "foundation"
    selected_preset: Optional[str] = None
    decisions: Dict[str, DecisionValue] = field(default_factory=dict)
    unresolved: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def apply_decision(
        self,
        question_id: str,
        value: Any,
        source: str = "user_selected",
        confidence: str = "high",
        note: str = "",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.decisions[question_id] = DecisionValue(
            value=value,
            source=source,
            confidence=confidence,
            note=note,
            inputs=inputs or {},
        )
        if question_id in self.unresolved:
            self.unresolved = [x for x in self.unresolved if x != question_id]
        self.updated_at = utc_now_iso()

    def get_value(self, question_id: str, default: Any = None) -> Any:
        item = self.decisions.get(question_id)
        return item.value if item else default

    def get_inputs(self, question_id: str) -> Dict[str, Any]:
        item = self.decisions.get(question_id)
        return item.inputs if item else {}

    def to_dict(self) -> JSONDict:
        return {
            "id": self.id,
            "user_goal": self.user_goal,
            "inferred_agent_type": self.inferred_agent_type,
            "current_stage": self.current_stage,
            "selected_preset": self.selected_preset,
            "decisions": {k: v.to_dict() for k, v in self.decisions.items()},
            "unresolved": list(self.unresolved),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: JSONDict) -> "PreSpecSession":
        session = cls(
            id=data.get("id", new_id("session")),
            user_goal=data["user_goal"],
            inferred_agent_type=data["inferred_agent_type"],
            current_stage=data.get("current_stage", "foundation"),
            selected_preset=data.get("selected_preset"),
            unresolved=data.get("unresolved", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
        )
        for key, value_data in data.get("decisions", {}).items():
            session.decisions[key] = DecisionValue(**value_data)
        return session


@dataclass
class DecisionBoard:
    session_id: str
    stage: str
    title: str
    summary: AgentSummary
    presets: List[PresetProfile]
    questions: List[DecisionQuestion]
    decisions: Dict[str, Any]
    impact_preview: List[ImpactItem] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=lambda: ["use_recommended", "confirm_stage", "save_draft"])

    def to_dict(self) -> JSONDict:
        return {
            "surface_type": "agent_design_board",
            "session_id": self.session_id,
            "stage": self.stage,
            "title": self.title,
            "summary": self.summary.to_dict(),
            "presets": [p.to_dict() for p in self.presets],
            "questions": [q.to_dict() for q in self.questions],
            "decisions": self.decisions,
            "impact_preview": [i.to_dict() for i in self.impact_preview],
            "next_actions": self.next_actions,
        }


@dataclass
class AgentDesignCard:
    title: str
    confirmed: List[str]
    unresolved: List[str]
    recommendation: str
    next_step: str

    def to_markdown(self) -> str:
        lines = [f"# Agent Design Card: {self.title}", ""]
        if self.recommendation:
            lines.extend(["## 推荐模式", "", self.recommendation, ""])
        lines.extend(["## 已确认", ""])
        if self.confirmed:
            lines.extend([f"- {item}" for item in self.confirmed])
        else:
            lines.append("- 暂无")
        lines.extend(["", "## 待确认", ""])
        if self.unresolved:
            lines.extend([f"- {item}" for item in self.unresolved])
        else:
            lines.append("- 暂无")
        lines.extend(["", "## 下一步", "", self.next_step, ""])
        return "\n".join(lines)
