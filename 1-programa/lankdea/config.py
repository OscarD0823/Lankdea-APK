from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


def resource_root() -> Path:
    """Devuelve la raíz correcta en código fuente, Android y PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class EditionConfig:
    edition: str = "local"
    name: str = "Lankdea Local"

    @classmethod
    def load(cls, path: Path | None = None) -> "EditionConfig":
        # Una configuración antigua no puede volver a activar servicios nube.
        return cls()
