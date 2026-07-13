from witness_qa.models import Confidence, Observation, Persona, ProjectProfile, ProjectType
from witness_qa.reasoning.providers import PromptBuilder


def test_prompt_builder_includes_visual_audit_for_mobile() -> None:
    persona = Persona(
        name="Visual bug hunter",
        goal="Find visual defects.",
        visual_focus=["clipping", "contrast", "button alignment"],
    )
    profile = ProjectProfile(
        target="mobile",
        project_type=ProjectType.MOBILE,
        confidence=Confidence.HIGH,
    )
    observation = Observation(
        adapter="mobile",
        summary="Login screen visible",
        text='{"screen":"login","keyboard":"hidden","safe_area":"top"}',
        errors=["CTA appears close to the bottom edge."],
    )
    prompt = PromptBuilder.build(
        profile=profile,
        persona=persona,
        adapter_name="mobile",
        allowed_actions=("click", "type", "wait"),
        history=[],
        observation=observation,
        previous_action="initial_observation",
        screenshot_attached=True,
    )
    assert '"visual_audit":{"enabled":true' in prompt
    assert "button drift" in prompt
    assert "safe-area" in prompt or "safe area" in prompt
    assert "actively search for layout breakage" in prompt


def test_prompt_builder_includes_simulator_grade_visual_audit() -> None:
    persona = Persona(
        name="Simulator visual QA director",
        goal="Find simulator defects.",
        visual_focus=["lane readability", "sensor overlays", "temporal stability"],
    )
    profile = ProjectProfile(
        target="sim",
        project_type=ProjectType.GAME,
        confidence=Confidence.HIGH,
        metadata={
            "game_engine": "unreal",
            "simulator_profile": "carla",
            "simulation_tags": ["simulator", "driving", "telemetry"],
        },
    )
    observation = Observation(
        adapter="game",
        summary="Driving scene visible",
        text='{"sensor":"front_camera","telemetry":"visible","lane":"center","weather":"fog"}',
        errors=["Traffic sign near the horizon appears hard to read."],
    )
    prompt = PromptBuilder.build(
        profile=profile,
        persona=persona,
        adapter_name="game",
        allowed_actions=("next_frame", "wait"),
        history=[],
        observation=observation,
        previous_action="initial_observation",
        screenshot_attached=True,
    )
    assert '"audit_depth":"exhaustive"' in prompt
    assert "vehicle/world clipping" in prompt
    assert "lane markings" in prompt
    assert "CARLA route/perception overlay conflicts" in prompt
    assert "weather, glare, fog" in prompt
