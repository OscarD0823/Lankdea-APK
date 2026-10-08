from pathlib import Path
import subprocess

import pytest
from cryptography.exceptions import InvalidTag

from scripts.source_archive import encrypt_source, decrypt_source


def test_source_archive_needs_password_and_never_overwrites(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    (root / "app.py").write_text("print('source private')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
    source = tmp_path / "source.lksource"
    encrypt_source(root, source, "a source-only phrase")
    assert b"source private" not in source.read_bytes()
    with pytest.raises(InvalidTag):
        decrypt_source(source, tmp_path / "wrong", "another phrase")
    assert not (tmp_path / "wrong").exists()
    decrypt_source(source, tmp_path / "result", "a source-only phrase")
    assert (tmp_path / "result/app.py").read_text() == "print('source private')\n"
    with pytest.raises(ValueError, match="carpeta nueva"):
        decrypt_source(source, tmp_path / "result", "a source-only phrase")
