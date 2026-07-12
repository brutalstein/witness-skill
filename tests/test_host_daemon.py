from __future__ import annotations

import http.client
import io
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from witness_qa.host_daemon import Handler, SessionHTTPServer, _private_write_json


def _handler(*, token: str = "secret", authorization: str | None = None, body: bytes = b""):
    handler = object.__new__(Handler)
    headers: dict[str, str] = {"Content-Length": str(len(body))}
    if authorization is not None:
        headers["Authorization"] = authorization
    handler.headers = headers
    handler.rfile = io.BytesIO(body)
    handler.server = SimpleNamespace(token=token)
    return handler


@pytest.mark.parametrize(
    ("authorization", "expected"),
    [
        ("Bearer secret", True),
        ("Bearer wrong", False),
        (None, False),
    ],
)
def test_authorized_uses_bearer_token(authorization: str | None, expected: bool) -> None:
    assert _handler(authorization=authorization)._authorized() is expected


def test_body_parses_json_object() -> None:
    payload = {"decision": {"expectation": "works"}}
    raw = json.dumps(payload).encode()
    assert _handler(body=raw)._body() == payload


def test_body_rejects_oversized_content_length() -> None:
    handler = _handler(body=b"{}")
    handler.headers["Content-Length"] = "2000001"
    with pytest.raises(ValueError, match="too large"):
        handler._body()


def test_body_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        _handler(body=b"[]")._body()


def test_private_write_json_atomically_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"old": true}\n', encoding="utf-8")

    _private_write_json(path, {"ok": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert not path.with_suffix(".json.tmp").exists()
    assert os.stat(path).st_mode & 0o077 == 0


def test_private_write_json_removes_temporary_file_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state.json"
    original_fdopen = os.fdopen

    def failing_fdopen(*args, **kwargs):
        original_fdopen(args[0], "wb").close()
        raise OSError("simulated write failure")

    monkeypatch.setattr(os, "fdopen", failing_fdopen)

    with pytest.raises(OSError, match="simulated"):
        _private_write_json(path, {"ok": False})

    assert not path.exists()
    assert not path.with_suffix(".json.tmp").exists()


def test_health_endpoint_requires_authentication_and_returns_state(tmp_path: Path) -> None:
    runtime = SimpleNamespace(status="active", output_dir=tmp_path)
    server = SessionHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime = runtime
    server.token = "health-token"
    server.state_path = tmp_path / "state.json"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        unauthorized = http.client.HTTPConnection(host, port, timeout=2)
        unauthorized.request("GET", "/health")
        response = unauthorized.getresponse()
        assert response.status == 403
        assert json.loads(response.read()) == {"ok": False, "error": "Unauthorized"}
        unauthorized.close()

        authorized = http.client.HTTPConnection(host, port, timeout=2)
        authorized.request("GET", "/health", headers={"Authorization": "Bearer health-token"})
        response = authorized.getresponse()
        assert response.status == 200
        payload = json.loads(response.read())
        assert payload["ok"] is True
        assert payload["status"] == "active"
        assert payload["output_dir"] == str(tmp_path)
        assert isinstance(payload["pid"], int)
        authorized.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_handler_status_and_not_found_routes(tmp_path: Path) -> None:
    runtime = SimpleNamespace(
        status="active",
        output_dir=tmp_path,
        steps=[1, 2],
        finalized=False,
        result=None,
    )
    server = SessionHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime = runtime
    server.token = "route-token"
    server.state_path = tmp_path / "state.json"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        for route, expected_status in [("/status", 200), ("/missing", 404)]:
            connection = http.client.HTTPConnection(host, port, timeout=2)
            connection.request("GET", route, headers={"Authorization": "Bearer route-token"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            assert response.status == expected_status
            if route == "/status":
                assert payload["turns"] == 2
                assert payload["terminal"] is False
            else:
                assert payload["error"] == "Not found"
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_request_decision_and_finish_endpoints(tmp_path: Path) -> None:
    class Runtime:
        def __init__(self) -> None:
            self.status = "active"
            self.output_dir = tmp_path
            self.steps: list[object] = []
            self.finalized = False
            self.result = None

        def request_payload(self):
            return {"ok": True, "turn": 3}

        def submit(self, decision, *, expected_turn):
            return {"ok": True, "decision": decision, "expected_turn": expected_turn}

        def finish(self, status):
            return {"ok": True, "status": status.value}

    server = SessionHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime = Runtime()
    server.token = "post-token"
    server.state_path = tmp_path / "state.json"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    headers = {"Authorization": "Bearer post-token", "Content-Type": "application/json"}

    try:
        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/request", headers=headers)
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["turn"] == 3
        connection.close()

        connection = http.client.HTTPConnection(host, port, timeout=2)
        body = json.dumps({"decision": {"expectation": "ok"}, "expected_turn": 3})
        connection.request("POST", "/decision", body=body, headers=headers)
        response = connection.getresponse()
        assert response.status == 200
        payload = json.loads(response.read())
        assert payload["expected_turn"] == 3
        assert payload["decision"] == {"expectation": "ok"}
        connection.close()

        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("POST", "/finish", body='{"status":"goal_reached"}', headers=headers)
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "goal_reached"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_post_rejects_missing_turn_and_unknown_route(tmp_path: Path) -> None:
    runtime = SimpleNamespace(status="active", output_dir=tmp_path)
    server = SessionHTTPServer(("127.0.0.1", 0), Handler)
    server.runtime = runtime
    server.token = "error-token"
    server.state_path = tmp_path / "state.json"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    headers = {"Authorization": "Bearer error-token", "Content-Type": "application/json"}

    try:
        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("POST", "/decision", body='{"decision":{}}', headers=headers)
        response = connection.getresponse()
        assert response.status == 400
        assert "expected_turn" in json.loads(response.read())["error"]
        connection.close()

        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("POST", "/missing", body="{}", headers=headers)
        response = connection.getresponse()
        assert response.status == 404
        assert json.loads(response.read())["error"] == "Not found"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
