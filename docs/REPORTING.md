# Reporting

A Witness report is an evidence index, not a model transcript dump.

## Finding contract

Each deduplicated finding contains:

- stable fingerprint and occurrence/persona context
- severity
- expectation
- observed fact
- user/player impact and judgment
- visual assessment when applicable
- black-box hypothesis, explicitly not a confirmed root cause
- suggested investigation/fix direction
- linked screenshot or structured evidence

Infrastructure failures are listed separately and never promoted to product findings.

## Artifacts

A session may emit:

- `report.md` and `report.html`
- `result.json`
- `junit.xml`
- `witness.sarif.json`
- `logs/session_trace.json`
- adapter-specific structured logs/transcripts
- screenshots or rendered terminal/API/game states

Campaign reports merge persona/journey results and deduplicate stable fingerprints while preserving occurrences.

## Reproducibility metadata

Results include Witness version, target revision, project type/confidence, adapter, provider/model, seed, start/end/duration, turn count, request/token/latency/cost data, and artifact paths.

## Redaction

Typed values are removed from structured traces. Sensitive HTTP headers and body fields are redacted. Evidence screenshots may still contain user-visible test data, so use synthetic accounts and treat output directories as test artifacts.

## CI behavior

`--fail-on` sets a severity threshold. Exit code `0` means no threshold-reaching finding; `1` means a product finding reached the threshold; `2` means configuration/infrastructure failure. JUnit and SARIF support test dashboards and code-scanning annotation.

## Remediation artifacts

`witness remediate` writes a separate request, workspace, generated patch, changed/removed-file list, agent stdout/stderr, verification transcript, JSON contract, and Markdown report. It never edits the discovery report and applies to source only after explicit verified approval.
