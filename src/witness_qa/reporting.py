from __future__ import annotations

import hashlib
import html
import json
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .models import (
    CampaignResult,
    Confidence,
    Finding,
    Judgment,
    OverallStatus,
    Persona,
    ProjectProfile,
    SessionMetadata,
    SessionResult,
    SessionStep,
    Severity,
    UsageMetrics,
)
from .utils import atomic_write_json, atomic_write_text, ensure_dir

SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
    Severity.NONE: 5,
}


def finding_fingerprint(summary: str, expectation: str, project_type: str) -> str:
    normalized = " ".join((summary + "|" + expectation + "|" + project_type).lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def project_revision(root: str | None) -> str:
    if not root:
        return ""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


class ReportWriter:
    def __init__(self, output_dir: Path, formats: Iterable[str] | None = None) -> None:
        self.output_dir = output_dir
        self.formats = {
            item.lower() for item in (formats or ("markdown", "json", "html", "junit", "sarif"))
        }
        ensure_dir(output_dir)
        ensure_dir(output_dir / "logs")
        ensure_dir(output_dir / "screenshots")

    def build_findings(
        self, persona: Persona, steps: list[SessionStep], project_type: str = ""
    ) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[str] = set()
        for step in steps:
            decision = step.decision
            terminal_blocked = decision.next_action.kind.value == "goal_blocked"
            if (
                decision.judgment is not Judgment.MISMATCH
                and not terminal_blocked
                and decision.severity is Severity.NONE
            ):
                continue
            severity = decision.severity
            if severity is Severity.NONE:
                if terminal_blocked and decision.confidence is Confidence.HIGH:
                    severity = Severity.HIGH
                elif decision.confidence is Confidence.HIGH:
                    severity = Severity.MEDIUM
                elif decision.confidence is Confidence.MEDIUM:
                    severity = Severity.LOW
                else:
                    severity = Severity.INFO
            summary = decision.observation_summary.strip() or decision.reasoning.strip()
            fingerprint = finding_fingerprint(summary, decision.expectation, project_type)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            findings.append(
                Finding(
                    fingerprint=fingerprint,
                    persona=persona.name,
                    severity=severity,
                    summary=summary,
                    expectation=decision.expectation,
                    observation=decision.observation_summary,
                    evidence_path=step.observation.screenshot_path
                    or step.observation.structured_path,
                    reasoning=decision.reasoning,
                    hypothesis=decision.hypothesis_if_mismatch,
                    suggested_investigation=decision.suggested_investigation,
                    visual_assessment=decision.visual_assessment,
                    turn=step.turn,
                )
            )
        return sorted(
            findings, key=lambda finding: (SEVERITY_ORDER[finding.severity], finding.turn)
        )

    def write(
        self,
        *,
        profile: ProjectProfile,
        persona: Persona,
        steps: list[SessionStep],
        overall_status: OverallStatus,
        adapter: str,
        provider: str,
        model: str,
        started_at: datetime,
        infrastructure_errors: list[str],
        usage: UsageMetrics | None = None,
        seed: int = 0,
        budget_exceeded: bool = False,
        max_cost_usd: float | None = None,
    ) -> SessionResult:
        finished_at = datetime.now(UTC)
        duration = max(0.0, (finished_at - started_at).total_seconds())
        findings = self.build_findings(persona, steps, profile.project_type.value)
        metadata = SessionMetadata(
            adapter=adapter,
            provider=provider,
            model=model,
            project_type=profile.project_type,
            project_confidence=profile.confidence,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            turns=len(steps),
            witness_version=__version__,
            project_revision=project_revision(profile.project_root),
            usage=usage or UsageMetrics(),
            seed=seed,
        )
        report_rel = Path("report.md")
        trace_rel = Path("logs") / "session_trace.json"
        artifacts = {
            "markdown": str((self.output_dir / report_rel).resolve()),
            "json": str((self.output_dir / "result.json").resolve()),
            "html": str((self.output_dir / "report.html").resolve()),
            "junit": str((self.output_dir / "junit.xml").resolve()),
            "sarif": str((self.output_dir / "witness.sarif.json").resolve()),
        }
        result = SessionResult(
            overall_status=overall_status,
            personas_run=[persona.name],
            findings=findings,
            report_path=artifacts["markdown"],
            trace_path=str((self.output_dir / trace_rel).resolve()),
            profile=profile,
            metadata=metadata,
            infrastructure_errors=infrastructure_errors,
            budget_exceeded=budget_exceeded,
            max_cost_usd=max_cost_usd,
            artifact_paths={
                name: path
                for name, path in artifacts.items()
                if name in self.formats or name in {"markdown", "json"}
            },
        )
        trace = {
            "schema_version": "2.0",
            "manifest": {
                "witness_version": __version__,
                "project_revision": metadata.project_revision,
                "provider": provider,
                "model": model,
                "seed": seed,
            },
            "result": result.model_dump(mode="json"),
            "persona": persona.model_dump(mode="json"),
            "steps": [self._redacted_step(step) for step in steps],
        }
        atomic_write_json(self.output_dir / trace_rel, trace)
        atomic_write_json(self.output_dir / "result.json", result.model_dump(mode="json"))
        markdown = self._render_markdown(result=result, persona=persona, steps=steps)
        atomic_write_text(self.output_dir / report_rel, markdown)
        if "html" in self.formats:
            atomic_write_text(self.output_dir / "report.html", self._render_html(result, markdown))
        if "junit" in self.formats:
            self._write_junit(self.output_dir / "junit.xml", result)
        if "sarif" in self.formats:
            atomic_write_json(self.output_dir / "witness.sarif.json", self._sarif(result))
        return result

    @staticmethod
    def _redacted_step(step: SessionStep) -> dict:
        data = step.model_dump(mode="json")
        actions = [data.get("action"), data.get("decision", {}).get("next_action")]
        for action in actions:
            if not action:
                continue
            if action.get("kind") in {"type", "send_input"} and action.get("text"):
                action["text"] = "[REDACTED]"
            if action.get("headers"):
                for key in list(action["headers"]):
                    if key.lower() in {"authorization", "cookie", "x-api-key"}:
                        action["headers"][key] = "[REDACTED]"
            if isinstance(action.get("body"), dict):
                for key in list(action["body"]):
                    if any(
                        token in key.lower() for token in ("password", "secret", "token", "key")
                    ):
                        action["body"][key] = "[REDACTED]"
        return data

    def _render_markdown(
        self, *, result: SessionResult, persona: Persona, steps: list[SessionStep]
    ) -> str:
        status_label = result.overall_status.value.replace("_", " ").title()
        finding_count = len(result.findings)
        if result.budget_exceeded:
            summary = (
                f"Witness tested **{result.profile.target}** as **{persona.name}** and stopped "
                f"after exceeding the configured cost budget. Existing evidence was preserved. "
                f"Status: **{status_label}**."
            )
        elif result.infrastructure_errors:
            summary = f"Witness tested **{result.profile.target}** as **{persona.name}**, but infrastructure problems prevented a fully reliable conclusion. Status: **{status_label}**."
        elif finding_count:
            summary = f"Witness tested **{result.profile.target}** as **{persona.name}** and recorded **{finding_count} evidence-backed finding{'s' if finding_count != 1 else ''}**. Overall status: **{status_label}**."
        else:
            summary = f"Witness tested **{result.profile.target}** as **{persona.name}**. The observed flow ended with **{status_label}** and no mismatch findings were recorded."
        lines = [
            "# Witness QA Report",
            "",
            "## Summary",
            "",
            summary,
            "",
            "## Persona",
            "",
            f"- **Role:** {persona.role}",
            f"- **Goal:** {persona.goal}",
            f"- **Success criteria:** {persona.success_criteria}",
            f"- **Known constraints:** {persona.known_constraints}",
            f"- **Environment:** {persona.viewport}, {persona.locale}, {persona.network_profile}, {persona.color_scheme}",
            "",
            "## Findings",
            "",
        ]
        if not result.findings:
            lines.extend(["No evidence-backed product mismatch was recorded in this session.", ""])
        for index, finding in enumerate(result.findings, start=1):
            lines.extend(
                [
                    f"### {index}. [{finding.severity.value.upper()}] {finding.summary}",
                    "",
                    f"- **Fingerprint:** `{finding.fingerprint}`",
                    f"- **Expected:** {finding.expectation}",
                    f"- **Observed fact:** {finding.observation}",
                    f"- **Judgment:** {finding.reasoning}",
                    f"- **Visual assessment:** {finding.visual_assessment or 'No separate visual assessment.'}",
                    f"- **Black-box hypothesis:** {finding.hypothesis or 'No root-cause hypothesis was warranted.'}",
                    f"- **Suggested investigation:** {finding.suggested_investigation or 'Reproduce against the linked evidence and inspect the relevant boundary.'}",
                    f"- **Evidence:** [{finding.evidence_path}]({finding.evidence_path})"
                    if finding.evidence_path
                    else "- **Evidence:** No visual artifact was available.",
                    "",
                ]
            )
            if finding.evidence_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                lines.extend([f"![Finding {index} evidence]({finding.evidence_path})", ""])
        if result.max_cost_usd is not None:
            lines.extend(
                [
                    "## Cost Budget",
                    "",
                    f"- **Limit:** ${result.max_cost_usd:.6f}",
                    f"- **Estimated usage:** ${result.metadata.usage.estimated_cost_usd:.6f}",
                    f"- **Estimate available:** {result.metadata.usage.cost_estimate_available}",
                    f"- **Budget exceeded:** {result.budget_exceeded}",
                    "",
                ]
            )
        if result.infrastructure_errors:
            lines.extend(
                [
                    "## Witness Infrastructure Notes",
                    "",
                    *[f"- {error}" for error in result.infrastructure_errors],
                    "",
                ]
            )
        lines.extend(["## Full Narrative Trace", ""])
        for step in steps:
            action = step.action.human_summary() if step.action else "Initial observation"
            decision = step.decision
            lines.extend(
                [
                    f"<details><summary>Turn {step.turn}: {action}</summary>",
                    "",
                    f"- **Expectation:** {decision.expectation}",
                    f"- **Observation:** {decision.observation_summary}",
                    f"- **Judgment:** {decision.judgment.value} ({decision.confidence.value} confidence)",
                    f"- **Reasoning:** {decision.reasoning}",
                    f"- **Next action:** {decision.next_action.human_summary()} — {decision.next_action.reason}",
                    f"- **Observation delta:** `{json.dumps(step.observation.delta.model_dump(mode='json') if step.observation.delta else {}, ensure_ascii=False)}`",
                    f"- **Evidence:** [{step.observation.screenshot_path or step.observation.structured_path}]({step.observation.screenshot_path or step.observation.structured_path})",
                    "",
                    "</details>",
                    "",
                ]
            )
        meta = result.metadata
        lines.extend(
            [
                "## Session Metadata",
                "",
                f"- **Witness:** {meta.witness_version}",
                f"- **Project revision:** `{meta.project_revision or 'unknown'}`",
                f"- **Project type:** {meta.project_type.value}",
                f"- **Detection confidence:** {meta.project_confidence.value}",
                f"- **Adapter:** {meta.adapter}",
                f"- **Reasoning provider/model:** {meta.provider} / `{meta.model}`",
                f"- **Turns:** {meta.turns}",
                f"- **Duration:** {meta.duration_seconds:.2f}s",
                f"- **Provider requests:** {meta.usage.requests}",
                f"- **Tokens:** {meta.usage.input_tokens} input / {meta.usage.output_tokens} output",
                f"- **Estimated cost:** ${meta.usage.estimated_cost_usd:.6f}",
                f"- **Cost estimate available:** {meta.usage.cost_estimate_available}",
                f"- **Maximum cost:** ${result.max_cost_usd:.6f}"
                if result.max_cost_usd is not None
                else "- **Maximum cost:** not configured",
                f"- **Budget exceeded:** {result.budget_exceeded}",
                f"- **Started:** {meta.started_at.isoformat()}",
                f"- **Finished:** {meta.finished_at.isoformat()}",
                "",
                "### Detection Evidence",
                "",
            ]
        )
        for signal in result.profile.raw_signals:
            lines.append(
                f"- `{signal.source}` → **{signal.project_type.value}** (+{signal.weight:g}): {signal.detail}"
            )
        lines.extend(
            [
                "",
                "---",
                "",
                "Generated by Witness. Verify findings against the linked evidence before acting.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _render_html(result: SessionResult, markdown: str) -> str:
        cards = []
        for finding in result.findings:
            evidence = (
                f'<img src="{html.escape(finding.evidence_path)}" alt="Evidence">'
                if finding.evidence_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                else ""
            )
            cards.append(
                f'<section class="finding {finding.severity.value}"><h2>[{finding.severity.value.upper()}] {html.escape(finding.summary)}</h2><p><b>Observed:</b> {html.escape(finding.observation)}</p><p><b>Expected:</b> {html.escape(finding.expectation)}</p><p><b>Investigation:</b> {html.escape(finding.suggested_investigation)}</p>{evidence}</section>'
            )
        return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Witness QA Report</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;background:#f6f7f9;color:#17191d}}.finding{{background:white;padding:20px;margin:18px 0;border-left:6px solid #777;border-radius:8px;box-shadow:0 2px 10px #0001}}.critical{{border-color:#7a0019}}.high{{border-color:#c62828}}.medium{{border-color:#ef6c00}}.low{{border-color:#1565c0}}img{{max-width:100%;border:1px solid #ddd}}pre{{white-space:pre-wrap;background:#111;color:#eee;padding:16px;border-radius:8px}}</style></head><body><h1>Witness QA Report</h1><p>Status: <b>{html.escape(result.overall_status.value)}</b> · {len(result.findings)} finding(s)</p>{"".join(cards)}<details><summary>Raw Markdown</summary><pre>{html.escape(markdown)}</pre></details></body></html>"""

    @staticmethod
    def _write_junit(path: Path, result: SessionResult) -> None:
        suite = ET.Element(
            "testsuite",
            name="Witness QA",
            tests=str(max(1, len(result.findings))),
            failures=str(
                sum(
                    f.severity in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}
                    for f in result.findings
                )
            ),
            errors=str(len(result.infrastructure_errors)),
        )
        if not result.findings:
            ET.SubElement(
                suite,
                "testcase",
                name="agentic user journey",
                classname=result.metadata.adapter,
                time=f"{result.metadata.duration_seconds:.3f}",
            )
        for finding in result.findings:
            case = ET.SubElement(
                suite,
                "testcase",
                name=finding.summary[:200],
                classname=f"witness.{result.metadata.adapter}.{finding.persona}",
            )
            if finding.severity in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
                failure = ET.SubElement(
                    case, "failure", message=finding.summary, type=finding.severity.value
                )
                failure.text = f"Expected: {finding.expectation}\nObserved: {finding.observation}\nEvidence: {finding.evidence_path}"
            else:
                output = ET.SubElement(case, "system-out")
                output.text = finding.reasoning
        for error in result.infrastructure_errors:
            case = ET.SubElement(
                suite, "testcase", name="Witness infrastructure", classname="witness.infrastructure"
            )
            node = ET.SubElement(case, "error", message=error)
            node.text = error
        ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _sarif(result: SessionResult) -> dict:
        levels = {
            Severity.CRITICAL: "error",
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "note",
            Severity.INFO: "note",
            Severity.NONE: "none",
        }
        rules = []
        results = []
        for finding in result.findings:
            rule_id = f"WITNESS-{finding.fingerprint}"
            rules.append(
                {
                    "id": rule_id,
                    "name": "AgenticProductFinding",
                    "shortDescription": {"text": finding.summary},
                    "help": {"text": finding.suggested_investigation or finding.reasoning},
                }
            )
            item = {
                "ruleId": rule_id,
                "level": levels[finding.severity],
                "message": {"text": f"{finding.observation}\nExpected: {finding.expectation}"},
                "properties": {
                    "persona": finding.persona,
                    "severity": finding.severity.value,
                    "fingerprint": finding.fingerprint,
                },
            }
            if finding.evidence_path:
                item["locations"] = [
                    {"physicalLocation": {"artifactLocation": {"uri": finding.evidence_path}}}
                ]
            results.append(item)
        return {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {"driver": {"name": "Witness", "version": __version__, "rules": rules}},
                    "results": results,
                }
            ],
        }


class CampaignReportWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        ensure_dir(output_dir)

    def write(
        self,
        sessions: list[SessionResult],
        *,
        max_cost_usd: float | None = None,
        budget_exceeded: bool = False,
    ) -> CampaignResult:
        by_fingerprint: dict[str, Finding] = {}
        for session in sessions:
            for finding in session.findings:
                if finding.fingerprint in by_fingerprint:
                    current = by_fingerprint[finding.fingerprint]
                    current.occurrences += 1
                    if finding.persona not in current.persona:
                        current.persona += f", {finding.persona}"
                else:
                    by_fingerprint[finding.fingerprint] = finding.model_copy(deep=True)
        findings = sorted(
            by_fingerprint.values(), key=lambda item: (SEVERITY_ORDER[item.severity], item.summary)
        )
        if any(session.overall_status is OverallStatus.GOAL_BLOCKED for session in sessions):
            status = OverallStatus.GOAL_BLOCKED
        elif any(
            session.overall_status in {OverallStatus.MIXED, OverallStatus.INCONCLUSIVE}
            for session in sessions
        ):
            status = OverallStatus.MIXED
        else:
            status = OverallStatus.GOAL_REACHED
        markdown_path = self.output_dir / "campaign-report.md"
        html_path = self.output_dir / "campaign-report.html"
        junit_path = self.output_dir / "campaign-junit.xml"
        sarif_path = self.output_dir / "campaign.sarif.json"
        estimated_cost = round(
            sum(session.metadata.usage.estimated_cost_usd for session in sessions), 8
        )
        budget_exceeded = budget_exceeded or any(session.budget_exceeded for session in sessions)
        lines = [
            "# Witness Test Campaign",
            "",
            f"**Status:** {status.value}",
            f"**Sessions:** {len(sessions)}",
            f"**Unique findings:** {len(findings)}",
            f"**Estimated cost:** ${estimated_cost:.6f}",
            f"**Maximum cost:** ${max_cost_usd:.6f}"
            if max_cost_usd is not None
            else "**Maximum cost:** not configured",
            f"**Budget exceeded:** {budget_exceeded}",
            "",
            "## Coverage",
            "",
        ]
        for session in sessions:
            lines.append(
                f"- **{', '.join(session.personas_run)}** — {session.overall_status.value}, {session.metadata.turns} turns, {len(session.findings)} findings — [report]({session.report_path})"
            )
        lines.extend(["", "## Deduplicated Findings", ""])
        for finding in findings:
            lines.extend(
                [
                    f"### [{finding.severity.value.upper()}] {finding.summary}",
                    "",
                    f"- Personas: {finding.persona}",
                    f"- Occurrences: {finding.occurrences}",
                    f"- Fingerprint: `{finding.fingerprint}`",
                    f"- Evidence: {finding.evidence_path}",
                    "",
                ]
            )
        atomic_write_text(markdown_path, "\n".join(lines))
        campaign = CampaignResult(
            overall_status=status,
            sessions=sessions,
            findings=findings,
            personas_run=sorted({p for session in sessions for p in session.personas_run}),
            report_path=str(markdown_path.resolve()),
            junit_path=str(junit_path.resolve()),
            sarif_path=str(sarif_path.resolve()),
            html_path=str(html_path.resolve()),
            budget_exceeded=budget_exceeded,
            max_cost_usd=max_cost_usd,
            estimated_cost_usd=estimated_cost,
        )
        atomic_write_json(
            self.output_dir / "campaign-result.json", campaign.model_dump(mode="json")
        )
        pseudo = sessions[0] if sessions else None
        if pseudo:
            merged = pseudo.model_copy(update={"findings": findings, "overall_status": status})
            ReportWriter._write_junit(junit_path, merged)
            atomic_write_json(sarif_path, ReportWriter._sarif(merged))
        html_body = "".join(
            f"<li><b>{html.escape(f.severity.value.upper())}</b> {html.escape(f.summary)} ({f.occurrences})</li>"
            for f in findings
        )
        atomic_write_text(
            html_path,
            f"<!doctype html><html><body><h1>Witness Campaign</h1><p>{len(sessions)} sessions · {len(findings)} unique findings</p><ul>{html_body}</ul></body></html>",
        )
        return campaign
