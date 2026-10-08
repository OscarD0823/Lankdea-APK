import base64
import json

import pytest
from cryptography.fernet import Fernet

from lankdea.crypto import VaultCryptoError, decrypt_document
import lankdea.storage as storage
from lankdea.models import active_items, new_item
from lankdea.storage import (
    LEGACY_MARKER_FORMAT,
    LocalVaultRepository,
    migrate_legacy_file,
    retire_legacy_artifacts,
)


def test_repository_crud_and_backup(tmp_path):
    path = tmp_path / "vault.json"
    repository = LocalVaultRepository(path, "test")
    repository.create("contraseña maestra")
    item = new_item("note", "test", title="Hola", content="Mundo")
    repository.upsert_item(item)
    assert active_items(repository.snapshot())[0]["content"] == "Mundo"

    repository.lock()
    repository.unlock("contraseña maestra")
    repository.delete_item(item["id"])
    assert active_items(repository.snapshot()) == []
    assert path.with_suffix(".json.bak").exists()


def test_repository_stops_reading_at_the_envelope_limit(tmp_path, monkeypatch):
    path = tmp_path / "vault.json"
    path.write_bytes(b"{" + b"x" * 64)
    monkeypatch.setattr(storage, "MAX_ENVELOPE_FILE_BYTES", 64)
    with pytest.raises(VaultCryptoError, match="tamaño"):
        LocalVaultRepository(path, "test").read_envelope()


def test_change_passphrase_reencrypts(tmp_path):
    repository = LocalVaultRepository(tmp_path / "vault.json", "test")
    repository.create("contraseña anterior")
    repository.change_passphrase("contraseña nueva")
    backup = repository.path.with_suffix(repository.path.suffix + ".bak")
    with pytest.raises(VaultCryptoError):
        decrypt_document(json.loads(backup.read_text()), "contraseña anterior")
    decrypt_document(json.loads(backup.read_text()), "contraseña nueva")
    repository.lock()
    repository.unlock("contraseña nueva")
    assert repository.unlocked


def legacy_payload(items):
    key = Fernet.generate_key()
    encrypted = Fernet(key).encrypt(json.dumps(items).encode("utf-8")).decode("ascii")
    return {"fernet_key": key.decode("ascii"), "real_vault": encrypted}


def test_legacy_migration_retires_embedded_key_and_keeps_encrypted_backup(tmp_path):
    legacy = tmp_path / "lankdea_cofre.json"
    items = [{"type": "message", "title": "Antigua", "content": "nota"}]
    legacy.write_text(json.dumps(legacy_payload(items)), encoding="utf-8")
    repository = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json", "test")
    count = migrate_legacy_file(legacy, repository, "contraseña moderna")
    assert count == 1
    assert active_items(repository.snapshot())[0]["title"] == "Antigua"
    marker = json.loads(legacy.read_text(encoding="utf-8"))
    assert marker["format"] == LEGACY_MARKER_FORMAT
    assert "fernet_key" not in legacy.read_text(encoding="utf-8")
    encrypted_backup = legacy.with_suffix(".json.legacy.encrypted.bak")
    restored = decrypt_document(json.loads(encrypted_backup.read_text()), "contraseña moderna")
    assert active_items(restored)[0]["title"] == "Antigua"


def test_existing_self_decrypting_legacy_copies_are_retired_after_unlock(tmp_path):
    repository = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json", "test")
    repository.create("contraseña moderna")
    legacy = tmp_path / "lankdea_cofre.json"
    old_backup = legacy.with_suffix(".json.legacy.bak")
    payload = json.dumps(legacy_payload([{"title": "expuesta"}]))
    legacy.write_text(payload, encoding="utf-8")
    old_backup.write_text(payload, encoding="utf-8")

    assert retire_legacy_artifacts(legacy, repository) == 2
    assert "fernet_key" not in legacy.read_text(encoding="utf-8")
    assert "fernet_key" not in old_backup.read_text(encoding="utf-8")
    encrypted_backup = legacy.with_suffix(".json.legacy.encrypted.bak")
    decrypt_document(json.loads(encrypted_backup.read_text()), repository.passphrase)


def test_rotation_rekeys_automatic_legacy_backup_and_preserves_its_snapshot(tmp_path):
    legacy = tmp_path / "lankdea_cofre.json"
    legacy.write_text(json.dumps(legacy_payload([{"title": "Antigua", "content": "dato"}])), encoding="utf-8")
    repo = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json", "test")
    migrate_legacy_file(legacy, repo, "contraseña anterior")
    repo.upsert_item(new_item("note", title="Nueva", content="otro dato"))
    repo.change_passphrase("contraseña nueva")
    backup = legacy.with_suffix(".json.legacy.encrypted.bak")
    envelope = json.loads(backup.read_text())
    with pytest.raises(VaultCryptoError):
        decrypt_document(envelope, "contraseña anterior")
    assert [i["title"] for i in active_items(decrypt_document(envelope, "contraseña nueva"))] == ["Antigua"]


def test_external_legacy_backup_is_owned_after_restart(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    legacy = external / "old.json"
    legacy.write_text(json.dumps(legacy_payload([{"title": "Legado"}])))
    repo = LocalVaultRepository(tmp_path / "data/vault.json")
    migrate_legacy_file(legacy, repo, "contraseña anterior")
    assert not legacy.with_suffix(".json.legacy.encrypted.bak").exists()
    repo = LocalVaultRepository(repo.path)
    repo.unlock("contraseña anterior")
    repo.change_passphrase("contraseña nueva")
    envelope = json.loads((repo.path.parent / "old.json.legacy.encrypted.bak").read_text())
    with pytest.raises(VaultCryptoError):
        decrypt_document(envelope, "contraseña anterior")
    assert active_items(decrypt_document(envelope, "contraseña nueva"))[0]["title"] == "Legado"


@pytest.mark.parametrize("failure_at", [1, 2, 3])
def test_rotation_write_failure_restores_all_managed_copies(tmp_path, monkeypatch, failure_at):
    legacy = tmp_path / "lankdea_cofre.json"
    legacy.write_text(json.dumps(legacy_payload([{"title": "Legado"}])))
    repo = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json")
    migrate_legacy_file(legacy, repo, "contraseña anterior")
    real_write = storage._write_private_json_atomic
    calls = 0
    def failing_write(path, value):
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise OSError("simulated disk failure")
        real_write(path, value)
    monkeypatch.setattr(storage, "_write_private_json_atomic", failing_write)
    with pytest.raises(OSError):
        repo.change_passphrase("contraseña nueva")
    assert repo.passphrase == "contraseña anterior"
    for path in (repo.path, repo.path.with_suffix(".json.bak"), tmp_path / "lankdea_cofre.json.legacy.encrypted.bak"):
        decrypt_document(json.loads(path.read_text()), "contraseña anterior")


def test_rotation_double_disk_failure_locks_session(tmp_path, monkeypatch):
    repo = LocalVaultRepository(tmp_path / "vault.json")
    repo.create("contraseña anterior")
    def fail(*_):
        raise OSError("disk unavailable")
    monkeypatch.setattr(storage, "_write_private_json_atomic", fail)
    with pytest.raises(VaultCryptoError, match="recuperación"):
        repo.change_passphrase("contraseña nueva")
    assert not repo.unlocked


def test_corrupt_or_foreign_managed_backup_stops_before_changes(tmp_path):
    repo = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json")
    repo.create("contraseña anterior")
    backup = tmp_path / "lankdea_cofre.json.legacy.encrypted.bak"
    backup.write_text("{}")
    original = repo.path.read_bytes()
    with pytest.raises(VaultCryptoError):
        repo.change_passphrase("contraseña nueva")
    assert repo.path.read_bytes() == original
    foreign = LocalVaultRepository(tmp_path / "another.json")
    foreign.create("contraseña anterior")
    foreign.export_encrypted(backup)
    with pytest.raises(VaultCryptoError, match="otro cofre"):
        repo.change_passphrase("contraseña nueva")
    assert repo.path.read_bytes() == original


def test_pre_registry_custom_legacy_backup_is_discovered_from_marker(tmp_path):
    legacy = tmp_path / "old.json"
    legacy.write_text(json.dumps(legacy_payload([{"title": "Legado"}])))
    repo = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json")
    migrate_legacy_file(legacy, repo, "contraseña anterior")
    document = repo.snapshot()
    document["settings"].pop("legacy_backup_names")
    repo.replace(document)
    repo = LocalVaultRepository(repo.path)
    repo.unlock("contraseña anterior")
    repo.change_passphrase("contraseña nueva")
    envelope = json.loads(legacy.with_suffix(".json.legacy.encrypted.bak").read_text())
    with pytest.raises(VaultCryptoError):
        decrypt_document(envelope, "contraseña anterior")
    assert active_items(decrypt_document(envelope, "contraseña nueva"))[0]["title"] == "Legado"
