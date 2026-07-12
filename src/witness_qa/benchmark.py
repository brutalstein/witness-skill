from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import Finding


@dataclass
class BenchmarkScore:
    cases: int
    expected_findings: int
    detected_findings: int
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        return self.true_positives / max(1, self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        return self.true_positives / max(1, self.true_positives + self.false_negatives)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "cases": self.cases,
            "expected_findings": self.expected_findings,
            "detected_findings": self.detected_findings,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
        }


def score_findings(findings: list[Finding], ground_truth_path: Path) -> BenchmarkScore:
    truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    expected = truth.get("expected_findings") or []
    detected_text = [
        " ".join(
            " ".join(
                (
                    finding.summary,
                    finding.expectation,
                    finding.observation,
                    finding.reasoning,
                    finding.hypothesis,
                    finding.suggested_investigation,
                    finding.visual_assessment,
                )
            )
            .lower()
            .split()
        )
        for finding in findings
    ]
    matched_detected: set[int] = set()
    true_positives = 0
    for expected_item in expected:
        required = [str(item).lower() for item in expected_item.get("evidence_contains", [])]
        alternatives = [
            [str(item).lower() for item in group]
            for group in expected_item.get("evidence_any", [])
            if isinstance(group, list)
        ]
        phrase_groups = [required, *alternatives] if required else alternatives
        match = next(
            (
                index
                for index, text in enumerate(detected_text)
                if index not in matched_detected
                and (
                    any(all(phrase in text for phrase in group) for group in phrase_groups)
                    if phrase_groups
                    else expected_item.get("fingerprint") == findings[index].fingerprint
                )
            ),
            None,
        )
        if match is not None:
            matched_detected.add(match)
            true_positives += 1
    return BenchmarkScore(
        cases=1,
        expected_findings=len(expected),
        detected_findings=len(findings),
        true_positives=true_positives,
        false_positives=max(0, len(findings) - true_positives),
        false_negatives=max(0, len(expected) - true_positives),
    )
