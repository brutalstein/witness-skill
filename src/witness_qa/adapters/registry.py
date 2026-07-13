from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import ConfigurationError
from ..models import ProjectType
from .api import APIAdapter
from .base import Adapter
from .cli import CLIAdapter
from .electron import ElectronAdapter
from .game import GameAdapter
from .mobile import MobileAdapter
from .web import WebAdapter

REGISTRY: dict[ProjectType, type[Adapter]] = {
    ProjectType.WEB: WebAdapter,
    ProjectType.CLI: CLIAdapter,
    ProjectType.API: APIAdapter,
    ProjectType.GAME: GameAdapter,
    ProjectType.DESKTOP: ElectronAdapter,
    ProjectType.MOBILE: MobileAdapter,
}


def create_adapter(project_type: ProjectType, output_dir: Path, **options: Any) -> Adapter:
    adapter_class = REGISTRY.get(project_type)
    if adapter_class is None:
        supported = ", ".join(kind.value for kind in REGISTRY)
        raise ConfigurationError(
            f"No adapter is registered for project type '{project_type.value}'. "
            f"Supported types: {supported}. Use --adapter to correct detection if appropriate."
        )
    return adapter_class(output_dir, **options)
