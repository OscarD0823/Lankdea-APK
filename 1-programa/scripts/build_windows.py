"""Crea un instalador real por usuario; nunca incluye el cofre ni datos locales."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.release_lib import (
    INSTALLERS_ROOT,
    ROOT,
    project_version,
    sha256,
    source_commit,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", help="Ruta a ISCC.exe de Inno Setup 6")
    args = parser.parse_args()
    commit = source_commit()
    compiler = args.iscc or shutil.which("ISCC.exe")
    if not compiler:
        for folder in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            candidate = Path(os.environ.get(folder, "")) / "Inno Setup 6/ISCC.exe"
            if candidate.is_file():
                compiler = str(candidate)
                break
    if not compiler or not Path(compiler).is_file():
        raise SystemExit("Falta Inno Setup 6. Instálalo desde https://jrsoftware.org/isdl.php o usa --iscc.")
    version = project_version()
    output = INSTALLERS_ROOT / "windows"
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "KIVY_GL_BACKEND": "mock", "KIVY_NO_ARGS": "1",
           "KIVY_NO_CONFIG": "1", "KIVY_NO_FILELOG": "1"}
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--optimize",
        "2",
        "--log-level",
        "WARN",
        "--name",
        "Lankdea-PC",
        "--specpath",
        "build",
        "--icon",
        str(ROOT / "assets/cofre_icono.png"),
    ]
    for asset in ("assets/cofre_abierto_3d.png", "assets/cofre_banner.png", "assets/cofre_icono.png", "assets/cofre_atlas_gothic.png"):
        command += ["--add-data", f"{ROOT / asset};assets"]
    command += ["--add-data", f"{ROOT / 'assets/sounds'};assets/sounds",
                "--add-data", f"{ROOT / 'assets/fonts'};assets/fonts",
                "--add-data", f"{ROOT / 'assets/licenses'};assets/licenses", str(ROOT / "main.py")]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    executable = ROOT / "dist/Lankdea-PC.exe"
    subprocess.run([compiler, f"/DAppVersion={version}", f"/DSourceExe={executable}",
                    f"/DOutputPath={output}", f"/DLicensePath={ROOT.parent / 'LICENSE'}",
                    f"/DNoticesPath={ROOT.parent / 'THIRD-PARTY-NOTICES.txt'}",
                    str(INSTALLERS_ROOT / "configuracion-windows/Lankdea.iss")], check=True)
    installer = output / f"Lankdea-{version}-Instalador-Windows-x64.exe"
    write_json(output / "windows-build.json", {
        "schema": 1, "platform": "windows-x64", "version": version, "commit": commit,
        "file": installer.name, "sha256": sha256(installer), "size": installer.stat().st_size,
        "signing": "unsigned-authenticode", "data_policy": "preserve-existing-vault",
    })
    print(installer)


if __name__ == "__main__":
    main()
