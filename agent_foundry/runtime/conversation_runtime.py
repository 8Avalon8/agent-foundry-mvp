from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from agent_foundry.builder.conversation_orchestrator import handle_action_event, handle_user_reply, start_conversation
from agent_foundry.builder.decision_board import load_session, save_session
from agent_foundry.llm.provider import provider_from_name


JSONDict = Dict[str, Any]


class ConversationRuntime:
    """Stateful runtime facade for Web/A2UI clients."""

    def __init__(
        self,
        output_root: Path,
        *,
        provider_name: str = "offline",
        model: Optional[str] = None,
        run_dry_run: bool = True,
    ) -> None:
        self.output_root = output_root
        self.provider_name = provider_name
        self.model = model
        self.run_dry_run = run_dry_run
        self.provider = provider_from_name(provider_name, model=model)

    def start(self, user_goal: str, *, agent_type: Optional[str] = None, agent_name: Optional[str] = None) -> JSONDict:
        result = start_conversation(user_goal, provider=self.provider, explicit_type=agent_type)
        session_path = self._save(result.session)
        data = result.to_dict()
        data["session_path"] = str(session_path)
        data["agent_name"] = agent_name
        return data

    def respond(self, payload: JSONDict) -> JSONDict:
        session_id = str(payload.get("session_id", ""))
        if not session_id:
            raise ValueError("respond requires session_id")
        session = load_session(self._session_path(session_id))
        agent_name = payload.get("agent_name")
        if payload.get("action_event") is not None:
            result = handle_action_event(
                session,
                payload["action_event"],
                output_root=self.output_root,
                agent_name=agent_name,
                run_dry_run=self.run_dry_run,
                provider=self.provider,
            )
        elif payload.get("natural_language_reply") is not None:
            result = handle_user_reply(
                session,
                str(payload["natural_language_reply"]),
                provider=self.provider,
                output_root=self.output_root,
                agent_name=agent_name,
                run_dry_run=self.run_dry_run,
            )
        else:
            raise ValueError("respond requires action_event or natural_language_reply")
        session_path = self._save(result.session)
        data = result.to_dict()
        data["session_path"] = str(session_path)
        return data

    def _save(self, session) -> Path:
        path = self._session_path(session.id)
        save_session(session, path)
        return path

    def _session_path(self, session_id: str) -> Path:
        return self.output_root / ".agent_foundry_sessions" / f"{session_id}.json"


def serve_conversation_api(
    *,
    host: str,
    port: int,
    output_root: Path,
    provider_name: str = "offline",
    model: Optional[str] = None,
    run_dry_run: bool = True,
) -> None:
    runtime = ConversationRuntime(output_root, provider_name=provider_name, model=model, run_dry_run=run_dry_run)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
                if self.path == "/conversation/start":
                    result = runtime.start(
                        str(payload.get("user_goal", "")),
                        agent_type=payload.get("agent_type"),
                        agent_name=payload.get("agent_name"),
                    )
                elif self.path == "/conversation/respond":
                    result = runtime.respond(payload)
                else:
                    self._write_json({"error": f"unknown endpoint: {self.path}"}, status=404)
                    return
                self._write_json(result)
            except Exception as exc:
                self._write_json({"error": str(exc)}, status=400)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _read_json(self) -> JSONDict:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            return json.loads(raw or "{}")

        def _write_json(self, payload: JSONDict, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Conversation API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
