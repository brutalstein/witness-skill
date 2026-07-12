from pathlib import Path

from witness_qa.personas import load_persona


def test_builtin_persona_loads() -> None:
    persona = load_persona("first-time-user")
    assert persona.name == "First-time user"
    assert persona.goal


def test_inline_goal_becomes_persona() -> None:
    persona = load_persona("Create an account and reach the dashboard")
    assert persona.name == "Ad-hoc user"
    assert "dashboard" in persona.goal


def test_yaml_persona_loads(tmp_path: Path) -> None:
    path = tmp_path / "persona.yaml"
    path.write_text("name: Tester\ngoal: Verify help output\n", encoding="utf-8")
    persona = load_persona(str(path))
    assert persona.name == "Tester"
