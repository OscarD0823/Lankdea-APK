import json
import zipfile

import pytest

from scripts.create_package import create_package, verify_package
from scripts.release_lib import project_version, sha256, write_json
from scripts.extract_downloads import extract_downloads

COMMIT = "a" * 40


def receipts(tmp_path, signing="debug"):
    version = project_version()
    windows = tmp_path / "windows"
    android = tmp_path / "android"
    windows.mkdir()
    android.mkdir()
    exe = windows / f"Lankdea-{version}-Instalador-Windows-x64.exe"
    exe.write_bytes(b"MZ" + b"test" * 100)
    apk = android / f"Lankdea-{version}-Android-arm64.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("AndroidManifest.xml", "manifest de prueba")
        archive.writestr("classes.dex", "dex de prueba")
    result = []
    for path, platform in [(exe, "windows-x64"), (apk, "android-arm64")]:
        info = path.parent / "build.json"
        write_json(info, {"schema": 1, "platform": platform, "version": version, "commit": COMMIT,
                         "file": path.name, "sha256": sha256(path), "size": path.stat().st_size,
                         "signing": signing if platform.startswith("android") else "unsigned-authenticode",
                         "package": "app.lankdea.lankdealocal", "version_code": 30300,
                         "certificate_sha256": "b" * 64})
        result.append(info)
    return result


def test_package_contains_only_allowlisted_payload_and_matching_hashes(tmp_path):
    windows, android = receipts(tmp_path)
    (tmp_path / "vault.json").write_text("NEVER PACKAGE")
    path = create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT)
    manifest = verify_package(path)
    assert manifest["channel"] == "pruebas"
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 9
        assert "Copyright (c) 2026 OscarD0823" in archive.read("LICENSE.txt").decode()
        assert "SIL OPEN FONT LICENSE" in archive.read("THIRD-PARTY-NOTICES.txt").decode()
        assert "vault.json" not in archive.namelist()
        assert "AVISO-APK-DE-PRUEBAS.txt" in archive.namelist()
    with pytest.raises(FileExistsError):
        create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT)


def test_debug_cannot_be_published_as_stable(tmp_path):
    windows, android = receipts(tmp_path)
    with pytest.raises(ValueError, match="debug"):
        create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT, require_release=True)


def test_release_package_has_expected_filename_and_no_debug_warning(tmp_path):
    windows, android = receipts(tmp_path, signing="release")
    path = create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT, require_release=True)
    assert path.name == f"Lankdea-{project_version()}-Completo-Windows-Android.zip"
    assert verify_package(path)["channel"] == "distribucion"
    extract_downloads(path, tmp_path / "downloads", version=project_version(), commit=COMMIT)
    assert len(list((tmp_path / "downloads").iterdir())) == 8
    with pytest.raises(FileExistsError):
        extract_downloads(path, tmp_path / "downloads", version=project_version(), commit=COMMIT)
    with pytest.raises(ValueError, match="commit"):
        extract_downloads(path, tmp_path / "wrong", version=project_version(), commit="0" * 40)


@pytest.mark.parametrize("field,value", [("version", "0.0.1"), ("commit", "0" * 40), ("sha256", "0" * 64), ("file", "../secret.key")])
def test_mixed_stale_or_tampered_artifacts_are_rejected(tmp_path, field, value):
    windows, android = receipts(tmp_path)
    info = json.loads(android.read_text())
    info[field] = value
    write_json(android, info)
    with pytest.raises(ValueError):
        create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT)


def test_corrupted_zip_is_detected(tmp_path):
    windows, android = receipts(tmp_path)
    path = create_package(windows, android, tmp_path / "out", version=project_version(), commit=COMMIT)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("secret.key", "unexpected")
    with pytest.raises(ValueError, match="ajenos"):
        verify_package(path)


def test_zip_bomb_metadata_is_rejected_before_decompression(tmp_path):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"0" * (2 * 1024 * 1024))
        archive.writestr("SHA256SUMS.txt", "")
    with pytest.raises(ValueError, match="compresión|tamaño"):
        verify_package(path)


def test_package_with_too_many_entries_is_rejected(tmp_path):
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(13):
            archive.writestr(f"entry-{index}", "x")
    with pytest.raises(ValueError, match="demasiados"):
        verify_package(path)
