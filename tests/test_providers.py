from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from witness_qa.reasoning.providers import AnthropicReasoningEngine, OpenAIReasoningEngine

DECISION = {
    "expectation": "The user should see the next step.",
    "action_taken": "initial_observation",
    "observation_summary": "The page is visible.",
    "judgment": "match",
    "confidence": "high",
    "reasoning": "The visible state is consistent with the expected starting point.",
    "hypothesis_if_mismatch": "",
    "severity": "none",
    "next_action": {
        "kind": "goal_reached",
        "target": "",
        "text": "",
        "key": "",
        "url": "",
        "direction": "",
        "command": "",
        "seconds": 0,
        "reason": "The test goal is complete.",
    },
}


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(
        self, response_payload: dict[str, Any], captured: dict[str, Any], **_: Any
    ) -> None:
        self.response_payload = response_payload
        self.captured = captured

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.captured.update({"url": url, **kwargs})
        return FakeResponse(self.response_payload)


def test_openai_provider_sends_vision_and_strict_schema(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    response = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(DECISION)}],
            }
        ],
    }
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "witness_qa.reasoning.providers.httpx.Client",
        lambda **kwargs: FakeClient(response, captured, **kwargs),
    )

    engine = OpenAIReasoningEngine(model="test-model", output_dir=tmp_path)
    result = engine._call(prompt="inspect", screenshot=("image/png", "YWJj"))

    assert result == DECISION
    payload = captured["json"]
    assert payload["input"][0]["content"][0]["type"] == "input_image"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True


def test_anthropic_provider_sends_vision_and_forced_strict_tool(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "name": "submit_witness_decision", "input": DECISION}],
    }
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "witness_qa.reasoning.providers.httpx.Client",
        lambda **kwargs: FakeClient(response, captured, **kwargs),
    )

    engine = AnthropicReasoningEngine(model="test-model", output_dir=tmp_path)
    result = engine._call(prompt="inspect", screenshot=("image/png", "YWJj"))

    assert result == DECISION
    payload = captured["json"]
    assert payload["messages"][0]["content"][0]["type"] == "image"
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["tools"][0]["strict"] is True
    assert payload["tool_choice"] == {"type": "tool", "name": "submit_witness_decision"}


def test_provider_tracks_configured_cost_and_uses_bounded_output(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    response = {
        "status": "completed",
        "usage": {"input_tokens": 1_000_000, "output_tokens": 500_000},
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(DECISION)}],
            }
        ],
    }
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "witness_qa.reasoning.providers.httpx.Client",
        lambda **kwargs: FakeClient(response, captured, **kwargs),
    )
    engine = OpenAIReasoningEngine(
        model="test-model",
        output_dir=tmp_path,
        input_cost_per_million=2.0,
        output_cost_per_million=4.0,
        max_output_tokens=777,
        image_detail="low",
    )
    engine._call(prompt="inspect", screenshot=("image/png", "YWJj"))
    assert engine.usage.cost_estimate_available is True
    assert engine.usage.estimated_cost_usd == 4.0
    assert captured["json"]["max_output_tokens"] == 777
    assert captured["json"]["input"][0]["content"][0]["detail"] == "low"
