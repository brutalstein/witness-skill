import json
from pathlib import Path

from witness_qa.replay import TraceReplay


def test_replay_extracts_nonterminal_actions(tmp_path: Path) -> None:
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "steps": [
                    {"decision": {"next_action": {"kind": "run_command", "command": "echo hi"}}},
                    {"decision": {"next_action": {"kind": "goal_reached"}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    replay = TraceReplay(trace)
    actions = replay.actions()
    assert len(actions) == 1
    assert actions[0].command == "echo hi"
