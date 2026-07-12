from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from witness_qa.cli import app
from witness_qa.integrations.github import format_findings_as_pr_comment, post_pr_comment


class FakeResponse:
    status_code = 201
    text = '{"id": 7}'

    def json(self) -> dict[str, Any]:
        return {"id": 7, "html_url": "https://github.test/comment/7"}


class FakeClient:
    def __init__(self, captured: dict[str, Any], **kwargs: Any) -> None:
        self.captured = captured
        self.captured["client_kwargs"] = kwargs

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.captured.update({"url": url, **kwargs})
        return FakeResponse()


def _result() -> dict[str, Any]:
    return {
        "overall_status": "goal_blocked",
        "profile": {"target": "demo"},
        "metadata": {"usage": {"estimated_cost_usd": 0.0123}},
        "report_path": "report.md",
        "findings": [
            {
                "severity": "high",
                "summary": "Signup failed",
                "expectation": "Account is created",
                "observation": "A server error is visible",
                "reasoning": "The user cannot continue",
                "suggested_investigation": "Inspect POST /signup",
                "evidence_path": "screenshots/004.png",
                "fingerprint": "abc123",
            }
        ],
    }


def test_formats_evidence_backed_pr_comment() -> None:
    comment = format_findings_as_pr_comment(_result())
    assert "[HIGH] Signup failed" in comment
    assert "Account is created" in comment
    assert "screenshots/004.png" in comment
    assert "abc123" in comment


def test_posts_expected_github_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "witness_qa.integrations.github.httpx.Client",
        lambda **kwargs: FakeClient(captured, **kwargs),
    )
    response = post_pr_comment(
        result=_result(), token="secret", repository="owner/repo", pr_number=42
    )
    assert response["id"] == 7
    assert captured["url"].endswith("/repos/owner/repo/issues/42/comments")
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert "Signup failed" in captured["json"]["body"]


def test_cli_dry_run_and_missing_credentials(tmp_path: Path) -> None:
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps(_result()), encoding="utf-8")
    runner = CliRunner()
    dry = runner.invoke(app, ["post-github-comment", str(result_file), "--dry-run"])
    assert dry.exit_code == 0
    assert "Witness QA" in dry.stdout

    failed = runner.invoke(app, ["post-github-comment", str(result_file)])
    assert failed.exit_code == 2
