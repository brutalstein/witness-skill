from __future__ import annotations

from ..models import ActionKind

ACTION_PROPERTIES = {
    "kind": {"type": "string", "enum": [kind.value for kind in ActionKind]},
    "target": {"type": "string"},
    "source": {"type": "string"},
    "text": {"type": "string"},
    "key": {"type": "string"},
    "url": {"type": "string"},
    "direction": {"type": "string"},
    "command": {"type": "string"},
    "method": {"type": "string"},
    "path": {"type": "string"},
    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
    "body": {},
    "files": {"type": "array", "items": {"type": "string"}},
    "option": {"type": "string"},
    "tab_index": {"type": "integer"},
    "seconds": {"type": "number"},
    "reason": {"type": "string"},
}

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "expectation": {"type": "string"},
        "action_taken": {"type": "string"},
        "observation_summary": {"type": "string"},
        "judgment": {"type": "string", "enum": ["match", "mismatch", "uncertain"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reasoning": {"type": "string"},
        "hypothesis_if_mismatch": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low", "info", "none"],
        },
        "suggested_investigation": {"type": "string"},
        "visual_assessment": {"type": "string"},
        "next_action": {
            "type": "object",
            "additionalProperties": False,
            "properties": ACTION_PROPERTIES,
            "required": list(ACTION_PROPERTIES),
        },
    },
    "required": [
        "expectation",
        "action_taken",
        "observation_summary",
        "judgment",
        "confidence",
        "reasoning",
        "hypothesis_if_mismatch",
        "severity",
        "suggested_investigation",
        "visual_assessment",
        "next_action",
    ],
}
