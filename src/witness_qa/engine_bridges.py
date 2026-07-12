from __future__ import annotations

import os
import shutil
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from .errors import ConfigurationError

_SUPPORTED = {"unity", "unreal"}


class Traversable(Protocol):
    @property
    def name(self) -> str: ...

    def is_dir(self) -> bool: ...

    def iterdir(self): ...

    def read_bytes(self) -> bytes: ...


def available_engine_bridges() -> tuple[str, ...]:
    return tuple(sorted(_SUPPORTED))


def install_engine_bridge(engine: str, destination: Path, *, force: bool = False) -> list[Path]:
    """Atomically install a packaged Unity or Unreal bridge into ``destination``.

    Unity callers normally use ``Packages/com.witness.qa``. Unreal callers normally use
    ``Plugins/WitnessBridge``. Existing non-empty destinations are preserved unless ``force`` is
    explicit; a failed replacement is rolled back.
    """

    normalized = engine.strip().lower()
    if normalized not in _SUPPORTED:
        raise ConfigurationError(
            f"Unsupported engine bridge {engine!r}; choose one of {', '.join(sorted(_SUPPORTED))}"
        )
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()) and not force:
        raise ConfigurationError(
            f"Refusing to overwrite non-empty engine bridge destination {destination}; use --force"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / f".{destination.name}.witness-stage-{os.getpid()}"
    backup = destination.parent / f".{destination.name}.witness-backup-{os.getpid()}"
    _remove_path(stage)
    _remove_path(backup)
    stage.mkdir(parents=True)
    source = files("witness_qa").joinpath("resources", "engine_bridges", normalized)
    written: list[Path] = []
    try:
        _copy_tree(source, stage, written, stage)
        if destination.exists():
            destination.rename(backup)
        stage.rename(destination)
    except Exception:
        _remove_path(stage)
        if not destination.exists() and backup.exists():
            backup.rename(destination)
        raise
    else:
        _remove_path(backup)
    return [destination / relative for relative in written]


def _copy_tree(source: Traversable, destination: Path, written: list[Path], root: Path) -> None:
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _copy_tree(item, target, written, root)
        else:
            target.write_bytes(item.read_bytes())
            written.append(target.relative_to(root))


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()
