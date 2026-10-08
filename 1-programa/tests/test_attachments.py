from io import BytesIO
import json
import zipfile

import pytest

from lankdea.attachments import CHUNK_SIZE, MAX_FILE_SIZE, decrypt_chunk, validate_metadata
from lankdea.crypto import VaultCryptoError, decrypt_document
from lankdea.peer_sync import PeerSyncClient, PeerSyncServer, generate_pair_code
from lankdea.storage import LocalVaultRepository, VaultLockedError


def repository(path, name="pc"):
    repo = LocalVaultRepository(path, name)
    repo.create("frase elegida por la persona")
    return repo


def test_streaming_files_are_encrypted_and_authenticate_every_block(tmp_path):
    repo = repository(tmp_path / "vault.json")
    original = b"PRIVATE document contents" + b"a" * (CHUNK_SIZE + 33)
    item = repo.import_attachment(BytesIO(original), name="../informe.pdf", size=len(original))
    metadata = item["attachment"]
    assert metadata["filename"] == "informe.pdf"
    assert len(metadata["hashes"]) == 2
    assert b"PRIVATE" not in repo.path.read_bytes()
    assert metadata["key"].encode() not in repo.path.read_bytes()
    encrypted = repo.read_attachment_chunk(metadata["file_id"], 0)
    assert b"PRIVATE" not in encrypted
    with pytest.raises(VaultCryptoError):
        decrypt_chunk(metadata, 0, encrypted[:-1] + bytes([encrypted[-1] ^ 1]))
    with pytest.raises(VaultCryptoError):
        decrypt_chunk(metadata, 1, encrypted)
    result = BytesIO()
    repo.export_attachment(metadata["file_id"], result)
    assert result.getvalue() == original
    repo.lock()
    with pytest.raises(VaultLockedError):
        repo.export_attachment(metadata["file_id"], BytesIO())


def test_empty_file_size_and_traversal_limits(tmp_path):
    repo = repository(tmp_path / "vault.json")
    empty = repo.import_attachment(BytesIO(), name="empty.txt", size=0)
    assert len(empty["attachment"]["hashes"]) == 1
    with pytest.raises(VaultCryptoError):
        repo.import_attachment(BytesIO(), name="huge.mp4", size=MAX_FILE_SIZE + 1)
    with pytest.raises(VaultCryptoError):
        repo.attachments.path("../escape", 0)
    invalid = dict(empty["attachment"], file_id="../escape")
    with pytest.raises(VaultCryptoError):
        validate_metadata(invalid)
    with pytest.raises(VaultCryptoError):
        repo.import_attachment(BytesIO(b"incomplete"), name="file.txt", size=100)


def test_bundle_restore_and_password_rotation_include_files(tmp_path):
    repo = repository(tmp_path / "first.json")
    item = repo.import_attachment(BytesIO(b"secret photo"), name="foto.png", size=12)
    repo.change_passphrase("otra frase nueva")
    for path in (repo.path, repo.path.with_suffix(".json.bak")):
        with pytest.raises(VaultCryptoError):
            decrypt_document(json.loads(path.read_text()), "frase elegida por la persona")
    bundle = repo.export_bundle(tmp_path / "backup.lankdea")
    destination = LocalVaultRepository(tmp_path / "second.json")
    destination.create("frase distinta de destino")
    destination.restore_bundle(bundle, "otra frase nueva")
    result = BytesIO()
    destination.export_attachment(item["attachment"]["file_id"], result)
    assert result.getvalue() == b"secret photo"
    with zipfile.ZipFile(bundle, "a") as archive:
        archive.writestr("../escape", b"bad")
    with pytest.raises(VaultCryptoError):
        destination.restore_bundle(bundle, "otra frase nueva")
    assert not (tmp_path.parent / "escape").exists()


@pytest.mark.parametrize("extra_size", [0, CHUNK_SIZE * 2 + 47])
def test_peer_sync_transfers_files_both_ways_and_resumes(tmp_path, extra_size):
    desktop = repository(tmp_path / "desktop.json")
    mobile = repository(tmp_path / "mobile.json", "mobile")
    desktop_payload = b"pc image" + b"a" * extra_size
    mobile_payload = b"mobile video" + b"b" * extra_size
    desktop_item = desktop.import_attachment(BytesIO(desktop_payload), name="photo.png", size=len(desktop_payload))
    mobile_item = mobile.import_attachment(BytesIO(mobile_payload), name="video.mp4", size=len(mobile_payload))
    code = generate_pair_code()
    server = PeerSyncServer(desktop, code, "pc", host="127.0.0.1", port=0, broadcast=False)
    server.start()
    try:
        result = PeerSyncClient(mobile, code).sync("127.0.0.1", server.port)
        assert result["blocks_transferred"] == (6 if extra_size else 2)
        assert result["blocks_missing"] == 0
        for repo, item, expected in ((mobile, desktop_item, desktop_payload), (desktop, mobile_item, mobile_payload)):
            output = BytesIO()
            repo.export_attachment(item["attachment"]["file_id"], output)
            assert output.getvalue() == expected
        assert PeerSyncClient(mobile, code).sync("127.0.0.1", server.port)["blocks_transferred"] == 0
    finally:
        server.stop()
