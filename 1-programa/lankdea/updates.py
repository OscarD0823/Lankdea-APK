"""Consulta de versiones a petición; nunca descarga ni ejecuta instaladores."""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from . import __version__

REPOSITORY = "OscarD0823/Lankdea-APK"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    if not match:
        raise ValueError("Usa una versión estable mayor.menor.parche, por ejemplo 3.5.0.")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class UpdateResult:
    state: str
    message: str
    version: str = ""


def check_latest_release(current: str = __version__, *, http=requests) -> UpdateResult:
    try:
        response = http.get(
            API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Lankdea-Updater"},
            timeout=(4, 8),
        )
        if response.status_code in (401, 403, 404):
            return UpdateResult("unavailable", "No hay una versión pública accesible. "
                                "Abre GitHub e inicia sesión si tienes acceso, o recibe el ZIP del autor.")
        response.raise_for_status()
        release = response.json()
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            raise ValueError("No es una versión estable.")
        version = str(release.get("tag_name", "")).removeprefix("v")
        available = version_tuple(version)
        expected = f"Lankdea-{version}-Completo-Windows-Android.zip"
        if not any(isinstance(asset, dict) and asset.get("name") == expected
                   for asset in release.get("assets", [])):
            return UpdateResult("unavailable", "La versión publicada aún no tiene un paquete completo.")
        if available > version_tuple(current):
            return UpdateResult("available", f"Disponible {version}. Abre GitHub para descargar el ZIP. "
                                "Respalda el cofre antes de actualizar.", version)
        return UpdateResult("current", f"Tu versión {current} está al día respecto a las versiones públicas.", version)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return UpdateResult("unavailable", "No se pudo comprobar la versión ahora. "
                            "Puedes seguir usando el cofre sin conexión; inténtalo más tarde.")
