from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PROJECTS: dict[int, dict] = {}
NEXT_ID = 1

OPENAPI = {
    "openapi": "3.0.3",
    "info": {"title": "Witness sample API", "version": "1.0.0"},
    "paths": {
        "/projects": {
            "get": {"summary": "List projects"},
            "post": {"summary": "Create project"},
        },
        "/projects/{id}": {"get": {"summary": "Get project"}},
    },
}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._json(200, {"service": "sample-api", "docs": "/openapi.json"})
        elif path == "/openapi.json":
            self._json(200, OPENAPI)
        elif path == "/projects":
            self._json(200, list(PROJECTS.values()))
        elif path.startswith("/projects/"):
            try:
                project_id = int(path.rsplit("/", 1)[1])
            except ValueError:
                self._json(400, {"error": "invalid id"})
                return
            if project_id not in PROJECTS:
                self._json(404, {"error": "project not found"})
            else:
                self._json(200, PROJECTS[project_id])
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        global NEXT_ID
        if urlparse(self.path).path != "/projects":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "invalid JSON"})
            return
        name = payload.get("name") if isinstance(payload, dict) else None
        if not isinstance(name, str) or not name.strip():
            self._json(422, {"error": "name is required"})
            return
        project = {"id": NEXT_ID, "name": name.strip()}
        PROJECTS[NEXT_ID] = project
        NEXT_ID += 1
        self._json(201, project)

    def log_message(self, *_: object) -> None:
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
