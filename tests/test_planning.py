from witness_qa.models import Confidence, ProjectProfile, ProjectType
from witness_qa.planning import TestPlanner


def test_game_plan_includes_visual_journeys() -> None:
    profile = ProjectProfile(
        target="game", project_type=ProjectType.GAME, confidence=Confidence.HIGH
    )
    plan = TestPlanner().build(profile)
    assert len(plan.journeys) >= 5
    assert any("HUD" in journey.name for journey in plan.journeys)


def test_mobile_plan_includes_touch_journeys() -> None:
    profile = ProjectProfile(
        target="mobile", project_type=ProjectType.MOBILE, confidence=Confidence.HIGH
    )
    plan = TestPlanner().build(profile)
    assert len(plan.journeys) >= 5
    assert any("mobile" in journey.name.lower() for journey in plan.journeys)
    assert "keyboard overlap and safe-area clipping" in plan.risks
