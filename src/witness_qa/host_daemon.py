from __future__ import annotations

import argparse
import json
import os
import secrets
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .host_session import HostSessionRuntime
from .models import OverallStatus


def _private_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


class SessionHTTPServer(HTTPServer):
    runtime: HostSessionRuntime
    token: str
    state_path: Path


class Handler(BaseHTTPRequestHandler):
    server: SessionHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        return secrets.compare_digest(header, expected)

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guard(self) -> bool:
        if not self._authorized():
            self._write(403, {"ok": False, "error": "Unauthorized"})
            return False
        return True

    def _body(self) -> dict[str, Any]:
        size = int(self.headers.get("Content-Length", "0") or 0)
        if size > 2_000_000:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(size) if size else b"{}"
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        if not self._guard():
            return
        try:
            if self.path == "/health":
                payload = {
                    "ok": True,
                    "status": self.server.runtime.status,
                    "pid": os.getpid(),
                    "output_dir": str(self.server.runtime.output_dir),
                }
            elif self.path == "/request":
                payload = self.server.runtime.request_payload()
            elif self.path == "/status":
                payload = {
                    "ok": True,
                    "status": self.server.runtime.status,
                    "turns": len(self.server.runtime.steps),
                    "terminal": self.server.runtime.finalized,
                    "result": self.server.runtime.result.model_dump(mode="json")
                    if self.server.runtime.result
                    else None,
                }
            else:
                self._write(404, {"ok": False, "error": "Not found"})
                return
            self._write(200, payload)
        except Exception as exc:
            self._write(400, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        if not self._guard():
            return
        try:
            body = self._body()
            if self.path == "/decision":
                decision = body.get("decision", body)
                expected_turn = body.get("expected_turn")
                if not isinstance(decision, dict):
                    raise ValueError("decision must be a JSON object")
                if not isinstance(expected_turn, int):
                    raise ValueError("expected_turn is required and must be an integer")
                payload = self.server.runtime.submit(decision, expected_turn=expected_turn)
            elif self.path == "/finish":
                status = OverallStatus(body.get("status", OverallStatus.INCONCLUSIVE.value))
                payload = self.server.runtime.finish(status)
            else:
                self._write(404, {"ok": False, "error": "Not found"})
                return
            self._write(200, payload)
        except Exception as exc:
            self._write(400, {"ok": False, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    runtime = HostSessionRuntime(spec)
    server = SessionHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime = runtime
    server.token = secrets.token_urlsafe(32)
    server.state_path = args.state
    server.timeout = 0.5
    port = int(server.server_address[1])
    state = {
        "schema_version": "1.0",
        "pid": os.getpid(),
        "port": port,
        "token": server.token,
        "output_dir": str(runtime.output_dir),
        "created_at": time.time(),
    }
    args.state.parent.mkdir(parents=True, exist_ok=True)
    _private_write_json(args.state, state)
    runtime.start()
    finalized_at: float | None = None
    try:
        while not runtime.shutdown_requested:
            server.handle_request()
            if runtime.idle_expired():
                runtime.finish(OverallStatus.INCONCLUSIVE)
                break
            if runtime.finalized:
                finalized_at = finalized_at or time.monotonic()
                if time.monotonic() - finalized_at > 3:
                    break
    finally:
        if not runtime.finalized:
            runtime.finish(OverallStatus.INCONCLUSIVE)
        server.server_close()
        # Preserve state as a pointer to artifacts but remove the bearer token.
        final_state = {
            "schema_version": "1.0",
            "pid": os.getpid(),
            "port": port,
            "token": "",
            "output_dir": str(runtime.output_dir),
            "status": "finished",
            "result_path": runtime.result.artifact_paths.get("json", "") if runtime.result else "",
        }
        _private_write_json(args.state, final_state)


if __name__ == "__main__":
    main()
