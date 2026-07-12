from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

from ..errors import AdapterError
from ..models import ActionKind, ActionResult, AdapterAction, Observation, ProjectProfile
from ..utils import atomic_write_json, ensure_dir, process_group_kwargs, terminate_process_tree
from .base import Adapter


@dataclass
class APISession:
    profile: ProjectProfile
    client: httpx.Client
    base_url: str
    process: subprocess.Popen[Any] | None = None
    process_log_handle: Any | None = None
    exchanges: list[dict[str, Any]] = field(default_factory=list)
    openapi: dict[str, Any] | None = None
    observation_index: int = 0


class APIAdapter(Adapter):
    name = "api"
    supported_actions = ("http_request", "wait")

    def start(self, project_profile: ProjectProfile) -> APISession:
        if not project_profile.reachable_address:
            raise AdapterError("API project profile has no reachable address")
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        process = None
        log_handle = None
        if not project_profile.metadata.get("already_running") and project_profile.entry_point:
            log_handle = (self.output_dir / "logs" / "target-process.log").open(
                "w", encoding="utf-8"
            )
            process = subprocess.Popen(
                project_profile.entry_point,
                cwd=project_profile.project_root or ".",
                shell=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                **process_group_kwargs(),
                text=True,
            )
        self._wait(project_profile.reachable_address, process)
        client = httpx.Client(
            base_url=project_profile.reachable_address.rstrip("/") + "/",
            follow_redirects=True,
            timeout=float(self.options.get("request_timeout", 30)),
            headers={"user-agent": "Witness-QA/1.0"},
        )
        session = APISession(
            profile=project_profile,
            client=client,
            base_url=project_profile.reachable_address,
            process=process,
            process_log_handle=log_handle,
        )
        session.openapi = self._discover_openapi(client)
        return session

    def act(self, session_handle: APISession, action: AdapterAction) -> ActionResult:
        try:
            if action.kind is ActionKind.WAIT:
                time.sleep(max(0.1, action.seconds))
                return ActionResult(success=True, summary=action.human_summary())
            if action.kind is not ActionKind.HTTP_REQUEST:
                raise AdapterError(f"APIAdapter does not support action {action.kind.value}")
            method = (action.method or "GET").upper()
            path = action.path or action.url or action.target
            if not path:
                raise AdapterError("http_request requires path or url")
            started = time.monotonic()
            response = session_handle.client.request(
                method,
                path,
                headers=self._redact_headers_for_request(action.headers),
                json=action.body if action.body is not None else None,
            )
            elapsed = time.monotonic() - started
            content_type = response.headers.get("content-type", "")
            body: Any
            if "json" in content_type:
                try:
                    body = response.json()
                except ValueError:
                    body = response.text[:20000]
            else:
                body = response.text[:20000]
            exchange = {
                "method": method,
                "url": str(response.request.url),
                "request_headers": self._redact_headers(dict(response.request.headers)),
                "request_body": self._redact_value(action.body),
                "status": response.status_code,
                "response_headers": self._redact_headers(dict(response.headers)),
                "response_body": self._redact_value(body),
                "duration_ms": round(elapsed * 1000, 2),
            }
            session_handle.exchanges.append(exchange)
            return ActionResult(
                success=True,
                summary=f"{method} {path} returned {response.status_code}",
                metadata={"status": response.status_code, "duration_ms": exchange["duration_ms"]},
            )
        except Exception as exc:
            return ActionResult(
                success=False,
                summary=f"Could not perform {action.human_summary()}",
                infrastructure_error=f"API action failed: {exc}",
            )

    def observe(self, session_handle: APISession) -> Observation:
        session_handle.observation_index += 1
        index = session_handle.observation_index
        endpoints = self._endpoints(session_handle.openapi)
        state = {
            "base_url": session_handle.base_url,
            "openapi_detected": bool(session_handle.openapi),
            "available_endpoints": endpoints[:200],
            "last_exchange": session_handle.exchanges[-1] if session_handle.exchanges else None,
            "exchange_count": len(session_handle.exchanges),
        }
        structured_rel = Path("logs") / f"{index:03d}_api.json"
        atomic_write_json(self.output_dir / structured_rel, state)
        screenshot_rel = Path("screenshots") / f"{index:03d}_api_state.png"
        self._render_state(state, self.output_dir / screenshot_rel)
        last = state["last_exchange"]
        errors: list[str] = []
        if last and last["status"] >= 400:
            errors.append(f"HTTP {last['status']}: {last['method']} {last['url']}")
        return Observation(
            adapter=self.name,
            summary=(
                f"API at {session_handle.base_url}; no request made yet"
                if not last
                else f"{last['method']} {last['url']} returned {last['status']}"
            ),
            text=json.dumps(state, ensure_ascii=False, indent=2),
            screenshot_path=screenshot_rel.as_posix(),
            structured_path=structured_rel.as_posix(),
            errors=errors,
            metadata={
                "endpoint_count": len(endpoints),
                "exchange_count": len(session_handle.exchanges),
            },
        )

    def stop(self, session_handle: APISession) -> None:
        session_handle.client.close()
        if session_handle.process:
            terminate_process_tree(session_handle.process)
        if session_handle.process_log_handle:
            session_handle.process_log_handle.close()

    @staticmethod
    def _discover_openapi(client: httpx.Client) -> dict[str, Any] | None:
        for path in ("openapi.json", "swagger.json", "api/openapi.json", "docs/openapi.json"):
            try:
                response = client.get(path)
                if response.status_code == 200 and "json" in response.headers.get(
                    "content-type", ""
                ):
                    data = response.json()
                    if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
                        return data
            except (httpx.HTTPError, ValueError):
                continue
        return None

    @staticmethod
    def _endpoints(openapi: dict[str, Any] | None) -> list[dict[str, str]]:
        if not openapi:
            return []
        endpoints: list[dict[str, str]] = []
        for path, methods in (openapi.get("paths") or {}).items():
            if not isinstance(methods, dict):
                continue
            for method, operation in methods.items():
                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                }:
                    continue
                endpoints.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "summary": str((operation or {}).get("summary", "")),
                    }
                )
        return endpoints

    @staticmethod
    def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
        sensitive = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
        return {
            key: ("[REDACTED]" if key.lower() in sensitive else value)
            for key, value in headers.items()
        }

    @staticmethod
    def _redact_headers_for_request(headers: dict[str, str]) -> dict[str, str]:
        return dict(headers)

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[REDACTED]"
                    if any(token in key.lower() for token in ("password", "secret", "token", "key"))
                    else cls._redact_value(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact_value(item) for item in value]
        if isinstance(value, str) and len(value) > 20000:
            return value[:20000] + "…"
        return value

    @staticmethod
    def _wait(url: str, process: subprocess.Popen[Any] | None) -> None:
        deadline = time.monotonic() + 45
        with httpx.Client(follow_redirects=True, timeout=2) as client:
            while time.monotonic() < deadline:
                if process and process.poll() is not None:
                    raise AdapterError(f"API process exited with code {process.returncode}")
                try:
                    if client.get(url).status_code < 500:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.3)
        raise AdapterError(f"Timed out waiting for API at {url}")

    @staticmethod
    def _render_state(state: dict[str, Any], path: Path) -> None:
        text = json.dumps(state, ensure_ascii=False, indent=2)
        lines = text.splitlines()[-55:]
        font = ImageFont.load_default()
        image = Image.new("RGB", (1200, max(420, 26 + len(lines) * 16)), "#111418")
        draw = ImageDraw.Draw(image)
        draw.text((14, 10), "Witness API observation", font=font, fill="#ffffff")
        y = 34
        for line in lines:
            draw.text((14, y), line[:170], font=font, fill="#e5e9f0")
            y += 16
        image.save(path)
