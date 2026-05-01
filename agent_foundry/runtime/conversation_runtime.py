from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from agent_foundry.builder.conversation_orchestrator import handle_action_event, handle_user_reply, start_conversation
from agent_foundry.builder.decision_board import load_session, save_session
from agent_foundry.llm.provider import LLMProviderError, provider_from_name
from agent_foundry.runtime.codex_handoff import complete_design, handoff_payload, mark_completed_artifacts
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
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.output_root = output_root
        self.provider_name = provider_name
        self.model = model
        self.run_dry_run = run_dry_run
        self.host = host
        self.port = port
        self.provider_error = ""
        try:
            self.provider = provider_from_name(provider_name, model=model)
        except LLMProviderError as exc:
            self.provider = None
            self.provider_error = str(exc)

    def start(self, user_goal: str, *, agent_type: Optional[str] = None, agent_name: Optional[str] = None) -> JSONDict:
        self._raise_if_provider_unavailable()
        result = start_conversation(user_goal, provider=self.provider, explicit_type=agent_type)
        if agent_name:
            result.session.metadata["codex_agent_name"] = agent_name
        session_path = self._save(result.session)
        data = result.to_dict()
        data["session_path"] = str(session_path)
        data["agent_name"] = agent_name
        return data

    def codex_start_design(
        self,
        user_goal: str,
        *,
        host: str,
        port: int,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> JSONDict:
        data = self.start(user_goal, agent_type=agent_type, agent_name=agent_name)
        session = load_session(self._session_path(data["session_id"]))
        payload = handoff_payload(
            session,
            output_root=self.output_root,
            host=host,
            port=port,
            status_hint=data.get("status"),
            assistant_message=data.get("assistant_message", ""),
        )
        payload["session_path"] = data.get("session_path")
        return payload

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
        if result.status == "completed":
            mark_completed_artifacts(
                result.session,
                output_root=self.output_root,
                agent_dir=result.agent_dir,
                run_dir=result.run_dir,
                agent_name=agent_name,
            )
        session_path = self._save(result.session)
        data = result.to_dict()
        data["session_path"] = str(session_path)
        data.update(
            handoff_payload(
                result.session,
                output_root=self.output_root,
                host=self.host,
                port=self.port,
                status_hint=result.status,
                assistant_message=result.message,
                include_a2ui_tree=False,
            )
        )
        return data

    def codex_session(self, session_id: str, *, host: str, port: int) -> JSONDict:
        session = load_session(self._session_path(session_id))
        return handoff_payload(session, output_root=self.output_root, host=host, port=port)

    def codex_continue(self, session_id: str, *, host: str, port: int) -> JSONDict:
        self._raise_if_provider_unavailable()
        session = load_session(self._session_path(session_id))
        status = handoff_payload(session, output_root=self.output_root, host=host, port=port, include_a2ui_tree=False)["status"]
        if status == "completed":
            return handoff_payload(session, output_root=self.output_root, host=host, port=port)
        if status != "ready_to_build":
            return handoff_payload(session, output_root=self.output_root, host=host, port=port, status_hint=status)
        complete_design(
            session,
            output_root=self.output_root,
            agent_name=session.metadata.get("codex_agent_name"),
            run_dry_run=self.run_dry_run,
            provider=self.provider,
        )
        session = load_session(self._session_path(session_id))
        return handoff_payload(session, output_root=self.output_root, host=host, port=port, status_hint="completed")

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
    runtime = ConversationRuntime(output_root, provider_name=provider_name, model=model, run_dry_run=run_dry_run, host=host, port=port)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if path == "/health":
                self._write_json(runtime.health())
                return
            if path.startswith("/codex/session/"):
                session_id = path.rsplit("/", 1)[-1]
                try:
                    self._write_json(runtime.codex_session(session_id, host=host, port=port))
                except Exception as exc:
                    self._write_json({"error": str(exc)}, status=404)
                return
            if serve_web and path.startswith("/design/"):
                session_id = path.rsplit("/", 1)[-1]
                if not session_id:
                    self._write_html(render_builder_web_app({"error": "missing session_id"}), status=404)
                    return
                try:
                    runtime.codex_session(session_id, host=host, port=port)
                except Exception:
                    self._write_html(render_builder_web_app({"error": f"session not found: {session_id}", "session_id": session_id}), status=404)
                    return
                self._write_html(
                    render_builder_web_app(
                        {
                            "provider": provider_name,
                            "model": model or "",
                            "output_root": str(output_root),
                            "run_dry_run": run_dry_run,
                            "session_id": session_id,
                            "codex_mode": True,
                        }
                    )
                )
                return
            if serve_web and path in {"/", "/index.html"}:
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
            self._write_json({"error": f"unknown endpoint: {path}"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            try:
                parsed = urlparse(self.path)
                path = parsed.path
                payload = self._read_json()
                if path == "/conversation/start":
                    result = runtime.start(
                        str(payload.get("user_goal", "")),
                        agent_type=payload.get("agent_type"),
                        agent_name=payload.get("agent_name"),
                    )
                elif path == "/conversation/respond":
                    result = runtime.respond(payload)
                elif path == "/codex/start-design":
                    result = runtime.codex_start_design(
                        str(payload.get("user_goal", "")),
                        host=host,
                        port=port,
                        agent_type=payload.get("agent_type"),
                        agent_name=payload.get("agent_name"),
                    )
                elif path == "/codex/continue":
                    result = runtime.codex_continue(str(payload.get("session_id", "")), host=host, port=port)
                else:
                    self._write_json({"error": f"unknown endpoint: {path}"}, status=404)
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
