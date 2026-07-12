from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import yaml

from .errors import ConfigurationError
from .models import Persona

ALIASES = {
    "first-time-user": "first_time_user",
    "first_time_user": "first_time_user",
    "first time user": "first_time_user",
    "adversarial-user": "adversarial_user",
    "adversarial_user": "adversarial_user",
    "adversarial": "adversarial_user",
    "keyboard-only-user": "keyboard_only_user",
    "slow-mobile-user": "slow_mobile_user",
    "low-vision-user": "low_vision_user",
    "game-visual-director": "game_visual_director",
}


def built_in_persona_names() -> list[str]:
    directory = files("witness_qa").joinpath("builtin_personas")
    return sorted(
        item.name.removesuffix(".yaml")
        for item in directory.iterdir()
        if item.name.endswith(".yaml")
    )


def load_persona(value: str | None) -> Persona:
    if not value:
        value = "first_time_user"
    path = Path(value).expanduser()
    if path.is_file():
        return _load_persona_path(path)

    key = ALIASES.get(value.strip().lower(), value.strip().lower().replace("-", "_"))
    resource = files("witness_qa").joinpath("builtin_personas", f"{key}.yaml")
    if resource.is_file():
        return Persona.model_validate(yaml.safe_load(resource.read_text(encoding="utf-8")))

    if len(value.strip()) < 5:
        raise ConfigurationError(
            f"Unknown persona '{value}'. Use a built-in name, a YAML/JSON path, or a fuller goal."
        )
    return Persona(
        name="Ad-hoc user",
        goal=value.strip(),
        role="A realistic user whose behavior is guided by the supplied goal.",
    )


def _load_persona_path(path: Path) -> Persona:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
        return Persona.model_validate(data)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not load persona from {path}: {exc}") from exc
