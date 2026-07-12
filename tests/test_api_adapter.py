from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx

from witness_qa.adapters.api import APIAdapter
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


def test_api_adapter_discovers_openapi_and_sends_request(
    repo_root: Path, free_port: int, tmp_path: Path
) -> None:
    root = repo_root / "examples" / "sample_api"
    process = subprocess.Popen([sys.executable, "app.py", "--port", str(free_port)], cwd=root)
    url = f"http://127.0.0.1:{free_port}"
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=0.3).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    profile = ProjectProfile(
        target=url,
        project_type=ProjectType.API,
        reachable_address=url,
        confidence=Confidence.HIGH,
        metadata={"already_running": True},
    )
    adapter = APIAdapter(tmp_path)
    session = adapter.start(profile)
    try:
        initial = adapter.observe(session)
        result = adapter.act(
            session,
            AdapterAction(
                kind=ActionKind.HTTP_REQUEST,
                method="POST",
                path="/projects",
                body={"name": "Witness"},
            ),
        )
        final = adapter.observe(session)
    finally:
        adapter.stop(session)
        process.terminate()
        process.wait(timeout=5)
    assert initial.metadata["endpoint_count"] >= 2
    assert result.success
    assert '"status": 201' in final.text
    assert (tmp_path / final.screenshot_path).is_file()
