from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def sample_server(repo_root: Path, free_port: int) -> Iterator[str]:
    app_dir = repo_root / "examples" / "buggy_signup"
    process = subprocess.Popen(
        [sys.executable, "app.py", "--port", str(free_port)],
        cwd=app_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{free_port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        process.kill()
        raise RuntimeError("sample server did not start")
    try:
        yield url
    finally:
        process.terminate()
        process.wait(timeout=5)
