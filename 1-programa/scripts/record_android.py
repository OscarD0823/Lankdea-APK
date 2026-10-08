"""Comprueba paquete, versión y firma reales antes de empaquetar la APK."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from scripts.release_lib import INSTALLERS_ROOT, project_version, sha256, source_commit, write_json


def certificate_fingerprint(output: str, signing: str) -> str:
    # Build Tools <=36: "Signer #1". Desde 37: "V2 Signer:", "V3 Signer:".
    # Se ignoran claves públicas y sellos de origen: solo certificados firmantes.
    label = r"(?:Signer #\d+|Signer \([^\r\n)]+\)|V[1-4](?:\.\d+)? Signer:)"
    fingerprints = {
        value.lower() for value in re.findall(
            rf"^{label}\s+certificate SHA-256 digest:\s*([0-9a-fA-F]{{64}})\s*$",
            output, re.MULTILINE,
        )
    }
    subjects = re.findall(rf"^{label}\s+certificate DN:\s*(.+)$", output, re.MULTILINE)
    if len(fingerprints) != 1 or not subjects:
        raise ValueError("No se encontró un único certificado firmante verificable en la salida de apksigner.")
    is_debug = any(re.search(r"(?:^|,)\s*CN\s*=\s*Android Debug(?:,|$)", subject, re.I)
                   for subject in subjects)
    if signing not in ("debug", "release") or is_debug != (signing == "debug"):
        raise ValueError("La firma APK no coincide con el canal declarado.")
    return fingerprints.pop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--aapt", required=True)
    parser.add_argument("--apksigner", required=True)
    parser.add_argument("--signing", required=True, choices=("debug", "release"))
    parser.add_argument("--expected-certificate", help="SHA-256 del certificado estable autorizado")
    args = parser.parse_args()
    version = project_version()
    badging = subprocess.check_output([args.aapt, "dump", "badging", str(args.apk)], text=True)
    identity = re.search(r"package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'", badging)
    if not identity or identity.group(1) != "app.lankdea.lankdealocal" or identity.group(3) != version:
        raise SystemExit("La APK no corresponde al paquete y versión Local actuales.")
    signed = subprocess.check_output([args.apksigner, "verify", "--print-certs", str(args.apk)], text=True)
    fingerprint = certificate_fingerprint(signed, args.signing)
    if args.expected_certificate is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", args.expected_certificate) or fingerprint != args.expected_certificate:
            raise SystemExit("La APK no está firmada con el certificado estable autorizado.")
    output = INSTALLERS_ROOT / "android"
    output.mkdir(parents=True, exist_ok=True)
    apk = output / f"Lankdea-{version}-Android-arm64.apk"
    shutil.copy2(args.apk, apk)
    write_json(output / "android-build.json", {
        "schema": 1, "platform": "android-arm64", "version": version, "commit": source_commit(),
        "file": apk.name, "sha256": sha256(apk), "size": apk.stat().st_size,
        "signing": args.signing, "certificate_sha256": fingerprint,
        "package": identity.group(1), "version_code": int(identity.group(2)),
    })
    print(apk)
    print(f"Certificado SHA-256 verificado ({args.signing}): {fingerprint}")


if __name__ == "__main__":
    main()
