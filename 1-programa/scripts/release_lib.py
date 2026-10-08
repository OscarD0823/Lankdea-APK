from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
INSTALLERS_ROOT = REPOSITORY_ROOT / "2-instaladores"


def project_version() -> str:
    match = re.search(r'__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"',
                      (ROOT / "lankdea/__init__.py").read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Versión inválida.")
    version = match.group(1)
    for name in ("pyproject.toml", "buildozer.local.spec"):
        value = re.search(r'^version = "?([0-9]+\.[0-9]+\.[0-9]+)',
                          (ROOT / name).read_text(encoding="utf-8"), re.MULTILINE)
        if not value or value.group(1) != version:
            raise ValueError(f"La versión de {name} no coincide con {version}.")
    return version


def source_commit() -> str:
    dirty = subprocess.check_output([
        "git", "status", "--porcelain", "--untracked-files=normal",
    ], cwd=REPOSITORY_ROOT, text=True)
    if dirty.strip():
        raise ValueError("Haz commit de los cambios de código y manual antes de compilar una entrega.")
    result = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", result):
        raise ValueError("Commit no válido.")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
