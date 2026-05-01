from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from agent_foundry.builder.conversation_orchestrator import handle_action_event, handle_user_reply, start_conversation
from agent_foundry.builder.decision_board import load_session, save_session
from agent_foundry.llm.provider import LLMProviderError, provider_from_name
from agent_foundry.runtime.web_app import render_builder_web_app


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
        self.provider_error = ""
        try:
            self.provider = provider_from_name(provider_name, model=model)
        except LLMProviderError as exc:
            self.provider = None
            self.provider_error = str(exc)

    def start(self, user_goal: str, *, agent_type: Optional[str] = None, agent_name: Optional[str] = None) -> JSONDict:
        self._raise_if_provider_unavailable()
        result = start_conversation(user_goal, provider=self.provider, explicit_type=agent_type)
        session_path = self._save(result.session)
        data = result.to_dict()
        data["session_path"] = str(session_path)
        data["agent_name"] = agent_name
        return data

    def respond(self, payload: JSONDict) -> JSONDict:
        self._raise_if_provider_unavailable()
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

    def _raise_if_provider_unavailable(self) -> None:
        if self.provider_error:
            raise ValueError(self.provider_error)

    def health(self) -> JSONDict:
        return {
            "status": "ok" if not self.provider_error else "degraded",
            "provider": self.provider_name,
            "model": getattr(self.provider, "model", self.model or ""),
            "output_root": str(self.output_root),
            "run_dry_run": self.run_dry_run,
            "provider_error": self.provider_error,
            "openai": {
                "api_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
                "base_url_configured": bool(os.environ.get("OPENAI_BASE_URL")),
            },
        }


def serve_conversation_api(
    *,
    host: str,
    port: int,
    output_root: Path,
    provider_name: str = "offline",
    model: Optional[str] = None,
    run_dry_run: bool = True,
    serve_web: bool = False,
) -> None:
    runtime = ConversationRuntime(output_root, provider_name=provider_name, model=model, run_dry_run=run_dry_run)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if self.path == "/health":
                self._write_json(runtime.health())
                return
            if serve_web and self.path in {"/", "/index.html"}:
                self._write_html(
                    render_builder_web_app(
                        {
                            "provider": provider_name,
                            "model": model or "",
                            "output_root": str(output_root),
                            "run_dry_run": run_dry_run,
                        }
                    )
                )
                return
            self._write_json({"error": f"unknown endpoint: {self.path}"}, status=404)

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
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, html: str, status: int = 200) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    label = "Agent Foundry Web" if serve_web else "Conversation API"
    print(f"{label} listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
