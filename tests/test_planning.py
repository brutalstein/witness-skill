from witness_qa.models import Confidence, ProjectProfile, ProjectType
from witness_qa.planning import TestPlanner


def test_game_plan_includes_visual_journeys() -> None:
    profile = ProjectProfile(
        target="game", project_type=ProjectType.GAME, confidence=Confidence.HIGH
    )
    plan = TestPlanner().build(profile)
    assert len(plan.journeys) >= 5
    assert any("HUD" in journey.name for journey in plan.journeys)
