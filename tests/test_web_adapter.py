from pathlib import Path

import pytest

from witness_qa.adapters.web import WebAdapter
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


@pytest.mark.e2e
def test_web_adapter_captures_and_interacts(sample_server: str, tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=sample_server,
        project_type=ProjectType.WEB,
        reachable_address=sample_server,
        confidence=Confidence.HIGH,
        metadata={"already_running": True},
    )
    adapter = WebAdapter(tmp_path, headless=True)
    session = adapter.start(profile)
    try:
        initial = adapter.observe(session)
        assert "Create your account" in initial.text
        assert adapter.act(
            session, AdapterAction(kind=ActionKind.TYPE, target="Email", text="a@example.com")
        ).success
        assert adapter.act(
            session, AdapterAction(kind=ActionKind.TYPE, target="Password", text="correct-horse")
        ).success
        assert adapter.act(
            session, AdapterAction(kind=ActionKind.CLICK, target="Create account")
        ).success
        final = adapter.observe(session)
        assert "correct-horse" not in final.text
    finally:
        adapter.stop(session)
    assert "Unable to create account" in final.text
    assert (tmp_path / final.screenshot_path).is_file()
