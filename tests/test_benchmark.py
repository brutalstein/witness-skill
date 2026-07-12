import json
from pathlib import Path

from witness_qa.benchmark import score_findings
from witness_qa.models import Finding, Severity


def _finding(summary: str, visual: str = "") -> Finding:
    return Finding(
        persona="tester",
        severity=Severity.HIGH,
        summary=summary,
        expectation="stable UI",
        observation=summary,
        evidence_path="frame.png",
        reasoning="visible mismatch",
        hypothesis="layout",
        visual_assessment=visual,
        turn=1,
    )


def test_benchmark_matches_full_finding_evidence_and_alternatives(tmp_path: Path) -> None:
    truth = tmp_path / "truth.json"
    truth.write_text(
        json.dumps(
            {
                "expected_findings": [
                    {"evidence_contains": ["clipped"]},
                    {
                        "evidence_contains": ["misaligned"],
                        "evidence_any": [["panel", "shifts downward"]],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    score = score_findings(
        [
            _finding("Shield panel", "Confirmed clipped status label"),
            _finding("Panel shifts downward between frames"),
        ],
        truth,
    )
    assert score.true_positives == 2
    assert score.precision == 1
    assert score.recall == 1
