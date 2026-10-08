"""Extrae solo la lista de distribución de un ZIP oficial ya verificado."""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from scripts.create_package import verify_package
from scripts.release_lib import project_version, source_commit


def extract_downloads(package: Path, output: Path, *, version: str, commit: str) -> None:
    manifest = verify_package(package)
    if (manifest.get("channel"), manifest.get("version"), manifest.get("commit")) != ("distribucion", version, commit):
        raise ValueError("La descarga no es una entrega oficial del commit actual.")
    allowed = {f"Lankdea-{version}-Instalador-Windows-x64.exe",
               f"Lankdea-{version}-Android-arm64.apk", "Manual-Lankdea.html", "LEEME.txt",
               "LICENSE.txt", "THIRD-PARTY-NOTICES.txt"}
    if set(manifest["files"]) != allowed:
        raise ValueError("La entrega contiene archivos inesperados.")
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package) as archive:
        for name in sorted(allowed | {"manifest.json", "SHA256SUMS.txt"}):
            with archive.open(name) as source, (output / name).open("xb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract_downloads(args.package, args.output, version=project_version(), commit=source_commit())


if __name__ == "__main__":
    main()
