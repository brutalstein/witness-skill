from __future__ import annotations

import re
from pathlib import Path

from .models import ProjectProfile, ProjectType, TestJourney, TestPlan

DEFAULT_JOURNEYS: dict[ProjectType, list[tuple[str, str, str]]] = {
    ProjectType.WEB: [
        (
            "first-load",
            "First-load comprehension",
            "Open the product and identify the primary action without confusion.",
        ),
        (
            "primary-flow",
            "Primary user flow",
            "Complete the product's main advertised user journey.",
        ),
        (
            "validation",
            "Input validation and recovery",
            "Submit incomplete or invalid input and recover using the visible guidance.",
        ),
        (
            "keyboard",
            "Keyboard-only navigation",
            "Reach and use the primary action using only keyboard controls.",
        ),
        (
            "responsive",
            "Responsive visual integrity",
            "Verify the main flow remains readable and usable in a narrow viewport.",
        ),
        (
            "visual-audit",
            "Deep visual defect audit",
            "Inspect the main journey specifically for misalignment, overlap, clipping, hidden actions, contrast failures, and broken visual hierarchy.",
        ),
    ],
    ProjectType.DESKTOP: [
        (
            "launch",
            "Desktop launch and first window",
            "Launch the Electron application and verify the primary renderer becomes usable without startup errors.",
        ),
        (
            "primary-flow",
            "Primary desktop workflow",
            "Complete the main workflow using the visible renderer controls and verify native-window state remains coherent.",
        ),
        (
            "window-resize",
            "Window resize resilience",
            "Inspect clipping, overflow, focus, and responsive layout behavior across practical desktop window sizes.",
        ),
        (
            "keyboard",
            "Desktop keyboard navigation",
            "Complete the primary action using keyboard focus and shortcuts without losing visible focus state.",
        ),
        (
            "visual-audit",
            "Deep desktop visual audit",
            "Inspect window states for misalignment, clipped controls, overlap, unreadable contrast, and inconsistent hierarchy.",
        ),
    ],
    ProjectType.MOBILE: [
        (
            "launch",
            "App launch and first-run clarity",
            "Launch the mobile app and verify the first visible screen is understandable without hidden setup knowledge.",
        ),
        (
            "primary-flow",
            "Primary mobile journey",
            "Complete the app's main user flow using touch interactions and visible guidance only.",
        ),
        (
            "keyboard",
            "Text input and keyboard resilience",
            "Enter realistic mobile input, submit it, and verify the on-screen keyboard does not obscure critical controls or feedback.",
        ),
        (
            "scroll",
            "Scroll and viewport continuity",
            "Move through long content and verify sticky controls, navigation, and section boundaries remain coherent.",
        ),
        (
            "interruptions",
            "Interruption and resume safety",
            "Background or reopen the app and verify the visible state, progress, and messaging remain coherent.",
        ),
        (
            "visual-audit",
            "Deep mobile visual audit",
            "Inspect the mobile journey for button drift, safe-area clipping, keyboard obstruction, touch-target crowding, overlap, contrast failures, and hidden controls.",
        ),
    ],
    ProjectType.CLI: [
        (
            "help",
            "Help and discoverability",
            "Use --help and understand the primary command without reading source code.",
        ),
        ("happy-path", "Primary command", "Run the main command with representative valid input."),
        (
            "invalid-input",
            "Invalid input recovery",
            "Provide invalid input and verify a useful message and non-zero exit code.",
        ),
        (
            "interrupt",
            "Interactive interruption",
            "Interrupt a running command and verify the terminal recovers cleanly.",
        ),
    ],
    ProjectType.API: [
        (
            "discover",
            "API discoverability",
            "Discover available endpoints from OpenAPI or documentation.",
        ),
        (
            "create-read",
            "Create and retrieve resource",
            "Create a resource and retrieve the same state through the public API.",
        ),
        (
            "validation",
            "Schema validation",
            "Send malformed input and verify a safe, actionable client error.",
        ),
        (
            "not-found",
            "Missing resource",
            "Request a missing resource and verify a consistent not-found contract.",
        ),
    ],
    ProjectType.GAME: [
        (
            "first-frame",
            "First-frame visual hierarchy",
            "Inspect the opening frame for clear hierarchy, safe-area fit, readability, and coherent art direction.",
        ),
        (
            "hud",
            "HUD consistency",
            "Inspect gameplay HUD alignment, spacing, scale, contrast, z-order, and feedback consistency.",
        ),
        (
            "transitions",
            "State and transition continuity",
            "Compare consecutive frames for flicker, stale overlays, animation discontinuity, and state residue.",
        ),
        (
            "resolution",
            "Resolution and safe-area resilience",
            "Inspect multiple resolutions/aspect ratios for clipping, stretching, blur, and misplaced UI.",
        ),
        (
            "accessibility",
            "Visual accessibility",
            "Assess text readability, color contrast, icon comprehensibility, motion load, and critical feedback redundancy.",
        ),
    ],
}

SIMULATOR_JOURNEYS: list[tuple[str, str, str]] = [
    (
        "scene-plausibility",
        "Scene plausibility and actor collisions",
        "Inspect the scene for vehicle/world clipping, actor intersections, impossible overlaps, and spatial anomalies.",
    ),
    (
        "sensor-hud",
        "Sensor and HUD occlusion audit",
        "Inspect mirrors, cameras, telemetry, route cues, and overlays for occlusion, crowding, and alignment defects.",
    ),
    (
        "road-readability",
        "Road and signage readability",
        "Inspect lane markings, signs, route guidance, and world-space affordances for readability under current framing and lighting.",
    ),
    (
        "temporal-stability",
        "Temporal stability audit",
        "Compare frames or state transitions for ghosting, flicker, pop-in, debug residue, and continuity defects.",
    ),
]


class TestPlanner:
    def build(self, profile: ProjectProfile, explicit_goals: list[str] | None = None) -> TestPlan:
        journeys = [
            TestJourney(
                id=f"custom-{index + 1}",
                name=f"Custom journey {index + 1}",
                goal=goal,
                priority="high",
                source="config",
            )
            for index, goal in enumerate(explicit_goals or [])
            if goal.strip()
        ]
        if not journeys:
            journeys = [
                TestJourney(
                    id=identifier,
                    name=name,
                    goal=goal,
                    priority="high" if index < 2 else "medium",
                    source="built-in",
                )
                for index, (identifier, name, goal) in enumerate(
                    DEFAULT_JOURNEYS.get(profile.project_type, [])
                )
            ]
        if profile.project_type is ProjectType.GAME and profile.metadata.get("simulator_profile"):
            existing_ids = {item.id for item in journeys}
            simulator_journeys = [
                TestJourney(
                    id=identifier,
                    name=name,
                    goal=goal,
                    priority="high",
                    source="built-in",
                )
                for identifier, name, goal in SIMULATOR_JOURNEYS
                if identifier not in existing_ids
            ]
            journeys = simulator_journeys + journeys
        journeys.extend(
            self._readme_journeys(profile, existing={item.goal.lower() for item in journeys})
        )
        risks = {
            ProjectType.WEB: [
                "asynchronous failures",
                "responsive clipping",
                "inaccessible controls",
                "silent network errors",
            ],
            ProjectType.DESKTOP: [
                (
                    "launch",
                    "Desktop launch and first window",
                    "Launch the Electron application and verify the primary renderer becomes usable without startup errors.",
                ),
                (
                    "primary-flow",
                    "Primary desktop workflow",
                    "Complete the main workflow using the visible renderer controls and verify native-window state remains coherent.",
                ),
                (
                    "window-resize",
                    "Window resize resilience",
                    "Inspect clipping, overflow, focus, and responsive layout behavior across practical desktop window sizes.",
                ),
                (
                    "keyboard",
                    "Desktop keyboard navigation",
                    "Complete the primary action using keyboard focus and shortcuts without losing visible focus state.",
                ),
            ],
            ProjectType.MOBILE: [
                "touch target ambiguity",
                "keyboard overlap and safe-area clipping",
                "scroll-state loss after resume",
                "platform-specific permission or navigation regressions",
            ],
            ProjectType.CLI: [
                "incorrect exit codes",
                "hung interactive processes",
                "destructive command suggestions",
                "unclear diagnostics",
            ],
            ProjectType.API: [
                "schema drift",
                "unsafe error leakage",
                "inconsistent status codes",
                "state propagation failures",
            ],
            ProjectType.GAME: [
                "resolution-dependent layout",
                "frame-to-frame inconsistency",
                "low-contrast feedback",
                "asset scaling and z-order defects",
            ],
        }.get(profile.project_type, [])
        if profile.project_type is ProjectType.GAME and profile.metadata.get("simulator_profile"):
            risks = [
                "vehicle or prop clipping against world geometry",
                "sensor or HUD overlays obscuring driving-critical scene content",
                "lane, sign, or route readability failures under lighting/weather changes",
                "temporal ghosting, pop-in, debug residue, or scene instability",
                *risks,
            ]
        return TestPlan(
            project_type=profile.project_type,
            journeys=journeys[:20],
            risks=risks,
            coverage_notes=[
                "Black-box coverage is evidence-driven, not a substitute for unit/integration coverage.",
                "Each journey should run in a fresh isolated state when the product supports reset fixtures.",
            ],
        )

    @staticmethod
    def _readme_journeys(profile: ProjectProfile, existing: set[str]) -> list[TestJourney]:
        text = str(profile.metadata.get("readme_excerpt") or "")
        if not text:
            return []
        candidates: list[str] = []
        for line in text.splitlines():
            cleaned = re.sub(r"^[\s>*#\-\d.)]+", "", line).strip()
            if 18 <= len(cleaned) <= 180 and any(
                token in cleaned.lower()
                for token in (
                    "user can",
                    "to create",
                    "to run",
                    "sign in",
                    "sign up",
                    "upload",
                    "export",
                    "play",
                    "start",
                )
            ):
                candidates.append(cleaned)
        result: list[TestJourney] = []
        for index, goal in enumerate(candidates[:5]):
            if goal.lower() in existing:
                continue
            result.append(
                TestJourney(id=f"readme-{index + 1}", name=goal[:60], goal=goal, source="README")
            )
        return result


def render_plan_markdown(plan: TestPlan, path: Path) -> None:
    lines = [
        "# Witness Test Plan",
        "",
        f"Project type: **{plan.project_type.value}**",
        "",
        "## Journeys",
        "",
    ]
    for index, journey in enumerate(plan.journeys, start=1):
        lines.extend(
            [
                f"### {index}. {journey.name}",
                "",
                f"- ID: `{journey.id}`",
                f"- Priority: {journey.priority}",
                f"- Source: {journey.source}",
                f"- Goal: {journey.goal}",
                "",
            ]
        )
    lines.extend(
        [
            "## Risks",
            "",
            *[f"- {risk}" for risk in plan.risks],
            "",
            "## Coverage Notes",
            "",
            *[f"- {note}" for note in plan.coverage_notes],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
