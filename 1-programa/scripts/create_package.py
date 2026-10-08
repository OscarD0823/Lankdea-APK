"""Une exclusivamente instalador, APK, instrucciones y manifiestos verificados."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.release_lib import INSTALLERS_ROOT, ROOT, project_version, sha256, source_commit


MAX_PACKAGE_ENTRIES = 12
MAX_ENTRY_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250
MAX_METADATA_BYTES = 1024 * 1024


def _validate_zip_metadata(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_PACKAGE_ENTRIES:
        raise ValueError("El ZIP contiene demasiados archivos.")
    names = [info.filename for info in infos]
    if len(set(names)) != len(names):
        raise ValueError("El ZIP contiene entradas duplicadas.")
    expanded = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise ValueError("El ZIP no puede contener entradas cifradas.")
        if info.file_size < 0 or info.file_size > MAX_ENTRY_UNCOMPRESSED:
            raise ValueError("Una entrada del ZIP supera el tamaño permitido.")
        expanded += info.file_size
        if expanded > MAX_TOTAL_UNCOMPRESSED:
            raise ValueError("El ZIP supera el tamaño expandido permitido.")
        if info.file_size > MAX_METADATA_BYTES:
            if info.compress_size <= 0 or info.file_size > info.compress_size * MAX_COMPRESSION_RATIO:
                raise ValueError("El ZIP tiene una relación de compresión insegura.")


def _read_zip_entry(archive: zipfile.ZipFile, name: str, maximum: int) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise ValueError(f"Falta {name} en el ZIP.") from exc
    if info.file_size > maximum:
        raise ValueError(f"{name} supera el tamaño permitido.")
    with archive.open(info) as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"{name} supera el tamaño permitido.")
    return data


def load_artifact(receipt_path: Path, platform: str, version: str, commit: str) -> tuple[dict, Path]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("schema"), receipt.get("platform"), receipt.get("version"), receipt.get("commit")) != (1, platform, version, commit):
        raise ValueError(f"{platform}: versión/commit no coinciden. Recompila ambos desde el mismo commit.")
    name = receipt.get("file", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
        raise ValueError("Nombre de artefacto inseguro.")
    path = receipt_path.parent / name
    if not path.is_file() or path.is_symlink() or path.stat().st_size != receipt.get("size") or sha256(path) != receipt.get("sha256"):
        raise ValueError(f"Artefacto modificado o inexistente: {name}")
    if platform == "windows-x64":
        with path.open("rb") as binary:
            if path.suffix != ".exe" or binary.read(2) != b"MZ":
                raise ValueError("No es un ejecutable Windows.")
    else:
        if path.suffix != ".apk" or receipt.get("signing") not in ("debug", "release"):
            raise ValueError("Canal Android no válido.")
        if receipt.get("package") != "app.lankdea.lankdealocal" or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("certificate_sha256", "")):
            raise ValueError("Identidad Android no válida.")
        if not isinstance(receipt.get("version_code"), int) or receipt["version_code"] <= 0:
            raise ValueError("versionCode Android inválido.")
        with zipfile.ZipFile(path) as apk:
            if not {"AndroidManifest.xml", "classes.dex"}.issubset(apk.namelist()) or apk.testzip():
                raise ValueError("APK incompleta o dañada.")
    return receipt, path


def verify_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        _validate_zip_metadata(archive)
        names = archive.namelist()
        if any("/" in name or "\\" in name or name in (".", "..") for name in names):
            raise ValueError("El ZIP contiene rutas inesperadas.")
        if archive.testzip():
            raise ValueError("ZIP corrupto.")
        manifest_bytes = _read_zip_entry(archive, "manifest.json", MAX_METADATA_BYTES)
        manifest = json.loads(manifest_bytes)
        files = manifest["files"]
        if set(names) != set(files) | {"manifest.json", "SHA256SUMS.txt"}:
            raise ValueError("El ZIP contiene archivos ajenos al paquete.")
        checks = []
        for name, info in files.items():
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != info["sha256"] or archive.getinfo(name).file_size != info["size"]:
                raise ValueError(f"Huella incorrecta: {name}")
            checks.append(f"{info['sha256']}  {name}\n")
        checks.append(f"{hashlib.sha256(manifest_bytes).hexdigest()}  manifest.json\n")
        checksum_bytes = _read_zip_entry(archive, "SHA256SUMS.txt", MAX_METADATA_BYTES)
        if checksum_bytes.decode("utf-8") != "".join(checks):
            raise ValueError("Lista SHA256SUMS inconsistente.")
    return manifest


def create_package(windows_info: Path, android_info: Path, output: Path, *, version: str, commit: str, require_release=False) -> Path:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Versión o commit no válidos.")
    windows, installer = load_artifact(windows_info, "windows-x64", version, commit)
    android, apk = load_artifact(android_info, "android-arm64", version, commit)
    preview = android["signing"] == "debug"
    if require_release and preview:
        raise ValueError("No se puede publicar una APK debug como actualización oficial. Configura una firma estable.")
    files = {installer.name: installer, apk.name: apk,
             "Manual-Lankdea.html": ROOT / "docs/Manual-Lankdea.html",
             "LEEME.txt": ROOT / "docs/LEEME.txt",
             "LICENSE.txt": ROOT.parent / "LICENSE",
             "THIRD-PARTY-NOTICES.txt": ROOT.parent / "THIRD-PARTY-NOTICES.txt"}
    manifest = {
        "schema": 1, "app": "Lankdea Local", "version": version, "commit": commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channel": "pruebas" if preview else "distribucion",
        "update_mode": "manual-full-installer", "windows": windows, "android": android,
        "integrity_note": "SHA-256 comprueba integridad, no sustituye una firma de editor.",
        "files": {name: {"sha256": sha256(file), "size": file.stat().st_size} for name, file in files.items()},
    }
    if preview:
        warning = ("PAQUETE DE PRUEBAS: APK firmada con Android Debug.\n"
                   "No garantiza actualización sobre otra APK. No desinstales tu cofre real.\n"
                   "Para distribuir actualizaciones usa la misma clave privada de publicación.\n")
        manifest["files"]["AVISO-APK-DE-PRUEBAS.txt"] = {"sha256": hashlib.sha256(warning.encode()).hexdigest(), "size": len(warning.encode())}
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    checks = "".join(f"{info['sha256']}  {name}\n" for name, info in manifest["files"].items())
    checks += f"{hashlib.sha256(data).hexdigest()}  manifest.json\n"
    output.mkdir(parents=True, exist_ok=True)
    suffix = "-PRUEBAS" if preview else ""
    target = output / f"Lankdea-{version}-Completo-Windows-Android{suffix}.zip"
    # Evita reemplazar silenciosamente una entrega ya distribuida.
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, file in files.items():
            archive.write(file, name)
        if preview:
            archive.writestr("AVISO-APK-DE-PRUEBAS.txt", warning)
        archive.writestr("manifest.json", data)
        archive.writestr("SHA256SUMS.txt", checks)
    verify_package(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--windows-info", type=Path,
        default=INSTALLERS_ROOT / "windows/windows-build.json",
    )
    parser.add_argument(
        "--android-info", type=Path,
        default=INSTALLERS_ROOT / "android/android-build.json",
    )
    parser.add_argument("--output", type=Path, default=INSTALLERS_ROOT)
    parser.add_argument("--require-release", action="store_true")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_package(args.verify), ensure_ascii=False, indent=2))
        return
    print(create_package(args.windows_info, args.android_info, args.output, version=project_version(),
                         commit=source_commit(), require_release=args.require_release))


if __name__ == "__main__":
    main()
