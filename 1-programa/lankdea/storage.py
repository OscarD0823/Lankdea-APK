from __future__ import annotations

import json
import os
import tempfile
import threading
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, BinaryIO

from cryptography.fernet import Fernet, InvalidToken

from .crypto import (
    MAX_CIPHERTEXT_BYTES,
    VaultCryptoError,
    decrypt_document,
    encrypt_document,
)
from .attachments import AttachmentStore, MAX_CHUNK_BYTES, MAX_FILES, MAX_STORAGE_SIZE, validate_metadata
from .models import active_items, merge_documents, new_document, new_item, normalize_document, now_iso


class VaultLockedError(RuntimeError):
    pass


MAX_ENVELOPE_FILE_BYTES = ((MAX_CIPHERTEXT_BYTES + 2) // 3) * 4 + 64 * 1024
MAX_LEGACY_FILE_BYTES = 8 * 1024 * 1024
LEGACY_MARKER_FORMAT = "lankdea-legacy-retired-v1"


def _write_private_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_json_limited(path: Path, maximum: int) -> Any:
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise VaultCryptoError("El archivo cifrado supera el tamaño permitido.")
        return json.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        raise
    except VaultCryptoError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise VaultCryptoError("No se pudo leer el archivo cifrado.") from exc


class LocalVaultRepository:
    def __init__(self, path: Path, device: str = "unknown") -> None:
        self.path = Path(path)
        self.device = device
        self._lock = threading.RLock()
        self._passphrase: str | None = None
        self._document: dict[str, Any] | None = None
        self._generation = 0
        self.attachments = AttachmentStore(self.path.with_suffix(self.path.suffix + ".files"))

    @property
    def exists(self) -> bool:
        with self._lock:
            return self.path.exists()

    @property
    def unlocked(self) -> bool:
        with self._lock:
            return self._document is not None and self._passphrase is not None

    @property
    def passphrase(self) -> str:
        with self._lock:
            if self._passphrase is None:
                raise VaultLockedError("El cofre está bloqueado.")
            return self._passphrase

    def create(self, passphrase: str, document: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self.exists:
                raise FileExistsError("El cofre ya existe.")
            self._passphrase = passphrase
            self._document = normalize_document(document or new_document(self.device), self.device)
            try:
                self._save()
            except Exception:
                self._passphrase = None
                self._document = None
                raise
            return self.snapshot()

    def unlock(self, passphrase: str) -> dict[str, Any]:
        with self._lock:
            generation = self._generation
            envelope = self.read_envelope()
        document = normalize_document(decrypt_document(envelope, passphrase), self.device)
        with self._lock:
            if generation != self._generation:
                raise VaultLockedError("La apertura fue cancelada.")
            self._passphrase = passphrase
            self._document = document
            return self.snapshot()

    def lock(self) -> None:
        with self._lock:
            self._generation += 1
            self._passphrase = None
            self._document = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._document is None:
                raise VaultLockedError("El cofre está bloqueado.")
            return deepcopy(self._document)

    def replace(self, document: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not self.unlocked:
                raise VaultLockedError("El cofre está bloqueado.")
            previous = self._document
            self._document = normalize_document(document, self.device)
            self._touch()
            try:
                self._save()
            except Exception:
                self._document = previous
                raise
            return self.snapshot()

    def upsert_item(self, item: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            document = self.snapshot()
            item = deepcopy(item)
            item["updated_at"] = now_iso()
            item["updated_by"] = self.device
            found = False
            for index, current in enumerate(document["items"]):
                if current.get("id") == item.get("id"):
                    document["items"][index] = item
                    found = True
                    break
            if not found:
                document["items"].append(item)
            return self.replace(document)

    def delete_item(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            document = self.snapshot()
            stamp = now_iso()
            for item in document["items"]:
                if item.get("id") == item_id:
                    item["deleted_at"] = stamp
                    item["updated_at"] = stamp
                    item["updated_by"] = self.device
                    break
            return self.replace(document)

    def update_settings(self, **values: Any) -> dict[str, Any]:
        with self._lock:
            document = self.snapshot()
            document.setdefault("settings", {}).update(values)
            return self.replace(document)

    def change_passphrase(self, new_passphrase: str) -> None:
        with self._lock:
            if not self.unlocked:
                raise VaultLockedError("El cofre está bloqueado.")
            previous_passphrase = self._passphrase
            previous_primary = self.read_envelope()
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            previous_backup = (
                _read_json_limited(backup, MAX_ENVELOPE_FILE_BYTES)
                if backup.exists()
                else None
            )
            new_envelope = encrypt_document(self._document or {}, new_passphrase)
            new_backup = encrypt_document(
                decrypt_document(previous_backup, self.passphrase), new_passphrase
            ) if previous_backup is not None else new_envelope
            # Copias de migración creadas por la app, no respaldos manuales.
            names = (self._document or {}).get("settings", {}).get("legacy_backup_names", [])
            if not isinstance(names, list) or len(names) > 8:
                raise VaultCryptoError("Registro de copias automáticas inválido.")
            names = list(names)
            if self.path.name == "lankdea_vault_v2.json":
                names.append("lankdea_cofre.json.legacy.encrypted.bak")
            # Versiones anteriores admitían nombres de legado personalizados.
            # Su marcador + vault_id permiten recuperar la propiedad después
            # de reiniciar, sin recifrar exportaciones manuales ni otro cofre.
            for candidate in self.path.parent.glob("*.legacy.encrypted.bak"):
                if candidate.name in names:
                    continue
                marker_path = candidate.with_name(candidate.name[:-len(".legacy.encrypted.bak")])
                try:
                    marker = _read_json_limited(marker_path, 64 * 1024)
                    if not isinstance(marker, dict) or marker.get("format") != LEGACY_MARKER_FORMAT or marker.get("encrypted_backup") != candidate.name:
                        continue
                    prior_document = decrypt_document(_read_json_limited(candidate, MAX_ENVELOPE_FILE_BYTES), self.passphrase)
                except (FileNotFoundError, VaultCryptoError):
                    # Si esta contraseña no la abre, no es un bypass de la clave
                    # que se está retirando; propiedad de esa copia desconocida.
                    continue
                if prior_document.get("vault_id") == (self._document or {}).get("vault_id"):
                    names.append(candidate.name)
            previous_legacy: dict[Path, dict] = {}
            replacement_legacy: dict[Path, dict] = {}
            if not all(isinstance(name, str) for name in names):
                raise VaultCryptoError("Registro de copias automáticas inválido.")
            for name in set(names):
                if not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name or not name.endswith(".legacy.encrypted.bak"):
                    raise VaultCryptoError("Nombre de copia automática inválido.")
                path = self.path.parent / name
                if not path.exists():
                    continue
                envelope = _read_json_limited(path, MAX_ENVELOPE_FILE_BYTES)
                old_document = decrypt_document(envelope, self.passphrase)
                if old_document.get("vault_id") != (self._document or {}).get("vault_id"):
                    raise VaultCryptoError("La copia automática pertenece a otro cofre; no se modificó la contraseña.")
                previous_legacy[path] = envelope
                replacement_legacy[path] = encrypt_document(old_document, new_passphrase)
            try:
                # Una rotación correcta debe retirar la contraseña anterior de
                # todas las copias administradas, no solo del archivo principal.
                _write_private_json_atomic(self.path, new_envelope)
                decrypt_document(self.read_envelope(), new_passphrase)
                _write_private_json_atomic(backup, new_backup)
                decrypt_document(
                    _read_json_limited(backup, MAX_ENVELOPE_FILE_BYTES),
                    new_passphrase,
                )
                for path, envelope in replacement_legacy.items():
                    _write_private_json_atomic(path, envelope)
                    decrypt_document(_read_json_limited(path, MAX_ENVELOPE_FILE_BYTES), new_passphrase)
            except Exception as error:
                # Intenta TODAS las restauraciones, incluso si el disco falla
                # durante una. Las escrituras son atómicas por archivo, no entre
                # archivos; nunca se anuncia éxito si una copia no pudo recifrarse.
                rollback_failed = False
                originals = {self.path: previous_primary, backup: previous_backup, **previous_legacy}
                for path, envelope in originals.items():
                    try:
                        if envelope is None:
                            path.unlink(missing_ok=True)
                        else:
                            _write_private_json_atomic(path, envelope)
                    except OSError:
                        rollback_failed = True
                self._passphrase = previous_passphrase
                if rollback_failed:
                    self.lock()
                    raise VaultCryptoError("Falló el disco durante el cambio y la recuperación. El cofre se bloqueó; conserva ambas contraseñas y revisa las copias antes de continuar.") from error
                raise
            self._passphrase = new_passphrase
            self._generation += 1

    def merge_envelope(self, envelope: dict[str, Any]) -> dict[str, int]:
        with self._lock:
            remote = decrypt_document(envelope, self.passphrase)
            local = self.snapshot()
            merged, stats = merge_documents(local, remote, self.device)
            if merged.get("items") != local.get("items"):
                self.replace(merged)
            return stats

    def read_envelope(self) -> dict[str, Any]:
        with self._lock:
            envelope = _read_json_limited(self.path, MAX_ENVELOPE_FILE_BYTES)
            if not isinstance(envelope, dict):
                raise VaultCryptoError("El archivo cifrado no es válido.")
            return envelope

    def export_encrypted(self, destination: Path) -> Path:
        with self._lock:
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            envelope = self.read_envelope()
            _write_private_json_atomic(destination, envelope)
            return destination

    def _session_check(self, generation: int) -> None:
        with self._lock:
            if not self.unlocked or generation != self._generation:
                raise VaultLockedError("El cofre se bloqueó; vuelve a abrirlo para continuar.")

    def import_attachment(self, source: BinaryIO, *, name: str, size: int) -> dict:
        with self._lock:
            self.snapshot()
            generation = self._generation
            if sum(i["type"] == "file" for i in active_items(self.snapshot())) >= MAX_FILES:
                raise VaultCryptoError("El cofre admite hasta 128 archivos activos.")
        metadata = self.attachments.import_stream(source, name=name, size=size,
                                                 check_session=lambda: self._session_check(generation))
        with self._lock:
            self._session_check(generation)
            item = new_item("file", self.device, title=metadata["filename"], attachment=metadata)
            self.upsert_item(item)
            return item

    def attachment_metadata(self, file_id: str) -> dict:
        with self._lock:
            for item in active_items(self.snapshot()):
                if item["type"] == "file" and item["attachment"]["file_id"] == file_id:
                    return validate_metadata(item["attachment"])
        raise VaultCryptoError("El archivo no pertenece al cofre abierto.")

    def read_attachment_chunk(self, file_id: str, index: int) -> bytes:
        with self._lock:
            return self.attachments.read(self.attachment_metadata(file_id), index)

    def receive_attachment_chunk(self, file_id: str, index: int, encrypted: bytes) -> None:
        with self._lock:
            self.attachments.receive(self.attachment_metadata(file_id), index, encrypted)

    def export_attachment(self, file_id: str, destination: BinaryIO) -> None:
        with self._lock:
            metadata = self.attachment_metadata(file_id)
            generation = self._generation
        self.attachments.export_stream(metadata, destination, lambda: self._session_check(generation))

    def export_bundle(self, destination: Path) -> Path:
        """Respaldo completo: ZIP sin compresión, con contenido ya cifrado."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # No sobrescribe respaldos ni archivos elegidos por accidente.
        try:
            with destination.open("xb") as stream:
                self.export_bundle_stream(stream)
        except Exception:
            # Elimina únicamente la copia que esta operación acaba de crear.
            if 'stream' in locals():
                destination.unlink(missing_ok=True)
            raise
        return destination

    def export_bundle_stream(self, stream: BinaryIO) -> None:
        with self._lock:
            document = self.snapshot()
            generation = self._generation
            envelope = self.read_envelope()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("vault.json", json.dumps(envelope, ensure_ascii=False))
            for item in active_items(document):
                if item["type"] != "file":
                    continue
                metadata = item["attachment"]
                for index in range(len(metadata["hashes"])):
                    self._session_check(generation)
                    archive.writestr(f"files/{metadata['file_id']}/{index:04d}.bin", self.attachments.read(metadata, index))
            self._session_check(generation)

    def restore_bundle(self, source: Path | BinaryIO, backup_passphrase: str | None = None) -> dict[str, int]:
        """Valida entradas exactas, tamaños y autenticidad; nunca usa extractall."""
        with self._lock:
            passphrase = backup_passphrase if backup_passphrase is not None else self.passphrase
            generation = self._generation
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > 1 + MAX_FILES * 128 or len({i.filename for i in infos}) != len(infos):
                raise VaultCryptoError("Respaldo inválido: demasiadas entradas o nombres duplicados.")
            if sum(i.file_size for i in infos) > MAX_STORAGE_SIZE + MAX_ENVELOPE_FILE_BYTES:
                raise VaultCryptoError("El respaldo supera el límite permitido.")
            if any(i.compress_type != zipfile.ZIP_STORED or i.file_size > max(MAX_ENVELOPE_FILE_BYTES, MAX_CHUNK_BYTES) for i in infos):
                raise VaultCryptoError("El respaldo contiene una entrada inválida.")
            with archive.open("vault.json") as stream:
                raw = stream.read(MAX_ENVELOPE_FILE_BYTES + 1)
            if len(raw) > MAX_ENVELOPE_FILE_BYTES:
                raise VaultCryptoError("El cofre del respaldo es demasiado grande.")
            envelope = json.loads(raw.decode("utf-8"))
            remote = normalize_document(decrypt_document(envelope, passphrase), self.device)
            expected = {"vault.json"}
            for item in active_items(remote):
                if item["type"] == "file":
                    metadata = item["attachment"]
                    expected.update(f"files/{metadata['file_id']}/{index:04d}.bin" for index in range(len(metadata["hashes"])))
            if expected != {i.filename for i in infos}:
                raise VaultCryptoError("El respaldo contiene archivos no reconocidos.")
            for item in active_items(remote):
                if item["type"] != "file":
                    continue
                metadata = item["attachment"]
                for index in range(len(metadata["hashes"])):
                    self._session_check(generation)
                    name = f"files/{metadata['file_id']}/{index:04d}.bin"
                    with archive.open(name) as stream:
                        encrypted = stream.read(MAX_CHUNK_BYTES + 1)
                    with self._lock:
                        self._session_check(generation)
                        self.attachments.receive(metadata, index, encrypted)
        with self._lock:
            self._session_check(generation)
            local = self.snapshot()
            merged, stats = merge_documents(local, remote, self.device)
            if merged.get("items") != local.get("items"):
                self.replace(merged)
            return stats

    def _touch(self) -> None:
        if self._document is None:
            return
        self._document["updated_at"] = now_iso()
        self._document["updated_by"] = self.device
        self._document["revision"] = int(self._document.get("revision", 0)) + 1

    def _save(self) -> None:
        if not self.unlocked:
            raise VaultLockedError("El cofre está bloqueado.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        envelope = encrypt_document(self._document or {}, self.passphrase)
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        if self.path.exists():
            previous = self.read_envelope()
            _write_private_json_atomic(backup, previous)
        _write_private_json_atomic(self.path, envelope)


def migrate_legacy_file(
    legacy_path: Path, repository: LocalVaultRepository, new_passphrase: str
) -> int:
    """Migra el formato heredado y retira sus copias autorrecuperables."""
    legacy_path = Path(legacy_path)
    try:
        state = _read_json_limited(legacy_path, MAX_LEGACY_FILE_BYTES)
        if not isinstance(state, dict):
            raise ValueError("legacy")
        key = state.get("fernet_key", "")
        encrypted = state.get("real_vault", "")
        if not isinstance(key, str) or not isinstance(encrypted, str):
            raise ValueError("legacy")
        items: list[dict[str, Any]] = []
        if encrypted:
            if not key:
                raise VaultCryptoError("La versión anterior no contiene su llave de migración.")
            items = json.loads(Fernet(key.encode("ascii")).decrypt(encrypted.encode("ascii")).decode("utf-8"))
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise ValueError("items")
    except (OSError, ValueError, InvalidToken, KeyError) as exc:
        raise VaultCryptoError("No se pudo migrar el cofre anterior.") from exc
    document = new_document(repository.device)
    document["items"] = items
    document["settings"]["totp_enabled"] = False
    repository.create(new_passphrase, document)
    retire_legacy_artifacts(legacy_path, repository)
    return len(active_items(repository.snapshot()))


def retire_legacy_artifacts(legacy_path: Path, repository: LocalVaultRepository) -> int:
    """Sustituye copias con llave embebida después de crear un respaldo moderno."""

    if not repository.unlocked:
        raise VaultLockedError("El cofre está bloqueado.")
    legacy_path = Path(legacy_path)
    candidates = (
        legacy_path,
        legacy_path.with_suffix(legacy_path.suffix + ".legacy.bak"),
    )
    exposed: list[Path] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            state = _read_json_limited(candidate, MAX_LEGACY_FILE_BYTES)
        except VaultCryptoError:
            continue
        if (
            isinstance(state, dict)
            and isinstance(state.get("fernet_key"), str)
            and bool(state.get("fernet_key"))
            and isinstance(state.get("real_vault"), str)
            and bool(state.get("real_vault"))
        ):
            exposed.append(candidate)
    if not exposed:
        return 0

    # La app es dueña de sus respaldos automáticos solo dentro de la carpeta
    # del cofre. Incluso al importar un legado externo, la copia moderna queda
    # aquí para poder recifrarse después de reiniciar el programa.
    encrypted_backup = repository.path.parent / legacy_path.with_suffix(
        legacy_path.suffix + ".legacy.encrypted.bak"
    ).name
    if encrypted_backup.parent.resolve() == repository.path.parent.resolve():
        settings = repository.snapshot().get("settings", {})
        names = settings.get("legacy_backup_names", [])
        if not isinstance(names, list) or len(names) >= 8:
            raise VaultCryptoError("Registro de copias automáticas inválido.")
        if encrypted_backup.name not in names:
            repository.update_settings(legacy_backup_names=[*names, encrypted_backup.name])
    repository.export_encrypted(encrypted_backup)
    decrypt_document(
        _read_json_limited(encrypted_backup, MAX_ENVELOPE_FILE_BYTES),
        repository.passphrase,
    )
    marker = {
        "format": LEGACY_MARKER_FORMAT,
        "message": "Copia heredada retirada; usa el respaldo cifrado moderno.",
        "encrypted_backup": encrypted_backup.name,
    }
    for candidate in exposed:
        _write_private_json_atomic(candidate, marker)
    return len(exposed)
