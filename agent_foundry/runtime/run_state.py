from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def new_run_state(run_type: str, *, agent_dir: Path | None = None, work_copy: Path | None = None) -> Dict[str, Any]:
    return {
        "run_type": run_type,
        "status": "running",
        "created_at": _now(),
        "updated_at": _now(),
        "agent_dir": str(agent_dir) if agent_dir else "",
        "work_copy": str(work_copy) if work_copy else "",
        "steps": {},
    }


def load_run_state(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "run_state.json"
    if not path.exists():
        return new_run_state("unknown")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run_state(run_dir: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = _now()
    (run_dir / "run_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_step(state: Dict[str, Any], step: str, status: str, detail: Dict[str, Any] | None = None) -> None:
    state.setdefault("steps", {})[step] = {"status": status, "updated_at": _now(), "detail": detail or {}}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
