"""Archivos cifrados por bloques; las llaves viven únicamente dentro del cofre.

Nunca crea una copia temporal en claro. El usuario debe exportar explícitamente
para entregar un archivo legible a otra aplicación.
"""
from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import re
import secrets
import tempfile
import threading
from pathlib import Path
from typing import BinaryIO, Callable, Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import VaultCryptoError

CHUNK_SIZE = 2 * 1024 * 1024
MAX_FILE_SIZE = 256 * 1024 * 1024
MAX_STORAGE_SIZE = 2 * 1024 * 1024 * 1024
MAX_FILES = 128
MAX_CHUNK_BYTES = CHUNK_SIZE + 28
ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def safe_filename(value: str) -> str:
    name = str(value).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if ord(c) >= 32 and c not in '<>:"/\\|?*')
    name = name.strip(" .")[:180]
    if not name or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}:
        return "archivo.bin"
    return name


def validate_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VaultCryptoError("Metadatos de archivo inválidos.")
    try:
        file_id = value["file_id"]
        size = value["size"]
        hashes = value["hashes"]
        key = base64.b64decode(value["key"], validate=True)
        if not isinstance(file_id, str) or not ID_PATTERN.fullmatch(file_id):
            raise ValueError("id")
        if type(size) is not int or not 0 <= size <= MAX_FILE_SIZE:
            raise ValueError("size")
        count = max(1, (size + CHUNK_SIZE - 1) // CHUNK_SIZE)
        if value.get("chunk_size") != CHUNK_SIZE or len(key) != 32:
            raise ValueError("key")
        if not isinstance(hashes, list) or len(hashes) != count:
            raise ValueError("chunks")
        if not all(isinstance(h, str) and HASH_PATTERN.fullmatch(h) for h in hashes):
            raise ValueError("hash")
        name = safe_filename(value.get("filename", "archivo.bin"))
        mime = str(value.get("mime_type") or "application/octet-stream")[:128]
        return {"file_id": file_id, "size": size, "chunk_size": CHUNK_SIZE,
                "hashes": list(hashes), "key": base64.b64encode(key).decode("ascii"),
                "filename": name, "mime_type": mime}
    except (KeyError, ValueError, TypeError) as exc:
        raise VaultCryptoError("Metadatos de archivo inválidos.") from exc


def _aad(metadata: dict, index: int) -> bytes:
    return f"lankdea:file:v1:{metadata['file_id']}:{index}:{metadata['size']}".encode("ascii")


def decrypt_chunk(metadata: dict, index: int, encrypted: bytes) -> bytes:
    metadata = validate_metadata(metadata)
    if type(index) is not int or not 0 <= index < len(metadata["hashes"]):
        raise VaultCryptoError("Bloque de archivo inválido.")
    expected_size = min(CHUNK_SIZE, metadata["size"] - index * CHUNK_SIZE)
    if len(encrypted) != expected_size + 28 or hashlib.sha256(encrypted).hexdigest() != metadata["hashes"][index]:
        raise VaultCryptoError("El archivo cifrado está incompleto o fue modificado.")
    try:
        return AESGCM(base64.b64decode(metadata["key"])).decrypt(encrypted[:12], encrypted[12:], _aad(metadata, index))
    except InvalidTag as exc:
        raise VaultCryptoError("No se pudo autenticar el archivo cifrado.") from exc


def write_private_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".chunk-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class AttachmentStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._io_lock = threading.RLock()

    def path(self, file_id: str, index: int) -> Path:
        if not ID_PATTERN.fullmatch(file_id) or type(index) is not int or not 0 <= index < MAX_FILE_SIZE // CHUNK_SIZE:
            raise VaultCryptoError("Ruta de archivo inválida.")
        return self.root / file_id / f"{index:04d}.bin"

    def _check_quota(self, extra: int) -> None:
        size = sum(p.stat().st_size for p in self.root.glob("*/*.bin") if p.is_file())
        if size + extra > MAX_STORAGE_SIZE:
            raise VaultCryptoError("El cofre alcanzó el límite de 2 GiB de archivos cifrados.")

    def import_stream(self, source: BinaryIO, *, name: str, size: int, check_session: Callable[[], None]) -> dict:
        if type(size) is not int or not 0 <= size <= MAX_FILE_SIZE:
            raise VaultCryptoError("Cada archivo puede ocupar como máximo 256 MiB.")
        self._check_quota(size + max(1, (size + CHUNK_SIZE - 1) // CHUNK_SIZE) * 28)
        key = secrets.token_bytes(32)
        metadata = {"file_id": secrets.token_hex(16), "filename": safe_filename(name),
                    "mime_type": mimetypes.guess_type(name)[0] or "application/octet-stream",
                    "size": size, "chunk_size": CHUNK_SIZE,
                    "key": base64.b64encode(key).decode("ascii"), "hashes": []}
        created: list[Path] = []
        try:
            count = max(1, (size + CHUNK_SIZE - 1) // CHUNK_SIZE)
            for index in range(count):
                check_session()
                expected = min(CHUNK_SIZE, size - index * CHUNK_SIZE)
                plain = source.read(expected)
                if len(plain) != expected:
                    raise VaultCryptoError("El archivo cambió mientras se guardaba.")
                nonce = secrets.token_bytes(12)
                encrypted = nonce + AESGCM(key).encrypt(nonce, plain, _aad(metadata, index))
                metadata["hashes"].append(hashlib.sha256(encrypted).hexdigest())
                path = self.path(metadata["file_id"], index)
                with self._io_lock:
                    self._check_quota(len(encrypted))
                    write_private_bytes(path, encrypted)
                created.append(path)
            if source.read(1):
                raise VaultCryptoError("El archivo cambió mientras se guardaba.")
            check_session()
            return validate_metadata(metadata)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            directory = self.root / metadata["file_id"]
            if directory.is_dir():
                directory.rmdir()
            raise

    def read(self, metadata: dict, index: int) -> bytes:
        metadata = validate_metadata(metadata)
        with self.path(metadata["file_id"], index).open("rb") as stream:
            data = stream.read(MAX_CHUNK_BYTES + 1)
        decrypt_chunk(metadata, index, data)
        return data

    def receive(self, metadata: dict, index: int, data: bytes) -> None:
        metadata = validate_metadata(metadata)
        decrypt_chunk(metadata, index, data)
        path = self.path(metadata["file_id"], index)
        with self._io_lock:
            if not path.exists():
                self._check_quota(len(data))
            write_private_bytes(path, data)

    def export_stream(self, metadata: dict, destination: BinaryIO, check_session: Callable[[], None]) -> None:
        metadata = validate_metadata(metadata)
        for index in range(len(metadata["hashes"])):
            check_session()
            destination.write(decrypt_chunk(metadata, index, self.read(metadata, index)))
        check_session()
