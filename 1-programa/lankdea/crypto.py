from __future__ import annotations

import base64
import json
import secrets
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


FORMAT = "lankdea-encrypted-v2"
AAD = b"lankdea:vault:v2"
DEFAULT_SCRYPT_N = 2**15
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1
SALT_BYTES = 16
NONCE_BYTES = 12
MAX_PLAINTEXT_BYTES = 8 * 1024 * 1024
MAX_CIPHERTEXT_BYTES = MAX_PLAINTEXT_BYTES + 16
MIN_SCRYPT_N = 2**14
MAX_SCRYPT_N = 2**17
MAX_SCRYPT_R = 8
MAX_SCRYPT_P = 4
MAX_SCRYPT_MEMORY = 128 * 1024 * 1024
MAX_SCRYPT_WORK = 2**20


class VaultCryptoError(ValueError):
    """El cofre no pudo validarse o descifrarse."""


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64d(value: str, *, maximum: int) -> bytes:
    if not isinstance(value, str) or len(value) > ((maximum + 2) // 3) * 4 + 4:
        raise VaultCryptoError("El archivo del cofre está dañado.")
    try:
        decoded = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise VaultCryptoError("El archivo del cofre está dañado.") from exc
    if len(decoded) > maximum:
        raise VaultCryptoError("El archivo del cofre está dañado.")
    return decoded


def _validate_scrypt_parameters(n: int, r: int, p: int) -> None:
    values = (n, r, p)
    if any(type(value) is not int for value in values):
        raise VaultCryptoError("Parámetros de cifrado no válidos.")
    if (
        n < MIN_SCRYPT_N
        or n > MAX_SCRYPT_N
        or n & (n - 1)
        or r < 1
        or r > MAX_SCRYPT_R
        or p < 1
        or p > MAX_SCRYPT_P
        or 128 * n * r > MAX_SCRYPT_MEMORY
        or n * r * p > MAX_SCRYPT_WORK
    ):
        raise VaultCryptoError("Parámetros de cifrado fuera del límite seguro.")


def derive_key(
    passphrase: str,
    salt: bytes,
    *,
    n: int = DEFAULT_SCRYPT_N,
    r: int = DEFAULT_SCRYPT_R,
    p: int = DEFAULT_SCRYPT_P,
) -> bytes:
    if not isinstance(passphrase, str) or not passphrase:
        raise VaultCryptoError("La contraseña maestra está vacía.")
    if not isinstance(salt, bytes) or len(salt) != SALT_BYTES:
        raise VaultCryptoError("La sal de cifrado no es válida.")
    _validate_scrypt_parameters(n, r, p)
    kdf = Scrypt(salt=salt, length=32, n=n, r=r, p=p)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_document(
    document: dict[str, Any],
    passphrase: str,
    *,
    salt: bytes | None = None,
    n: int = DEFAULT_SCRYPT_N,
    r: int = DEFAULT_SCRYPT_R,
    p: int = DEFAULT_SCRYPT_P,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise VaultCryptoError("Contenido del cofre no válido.")
    salt = secrets.token_bytes(SALT_BYTES) if salt is None else salt
    nonce = secrets.token_bytes(NONCE_BYTES)
    key = derive_key(passphrase, salt, n=n, r=r, p=p)
    plaintext = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise VaultCryptoError("El cofre supera el tamaño máximo permitido.")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    return {
        "format": FORMAT,
        "kdf": {"name": "scrypt", "n": n, "r": r, "p": p, "salt": _b64e(salt)},
        "cipher": {"name": "AES-256-GCM", "nonce": _b64e(nonce), "ciphertext": _b64e(ciphertext)},
    }


def decrypt_document(envelope: dict[str, Any], passphrase: str) -> dict[str, Any]:
    try:
        if envelope.get("format") != FORMAT:
            raise VaultCryptoError("Formato de cofre no compatible.")
        kdf = envelope["kdf"]
        cipher = envelope["cipher"]
        if not isinstance(kdf, dict) or not isinstance(cipher, dict):
            raise VaultCryptoError("El archivo cifrado no es válido.")
        if kdf.get("name") != "scrypt" or cipher.get("name") != "AES-256-GCM":
            raise VaultCryptoError("Algoritmo de cifrado no compatible.")
        n, r, p = kdf["n"], kdf["r"], kdf["p"]
        _validate_scrypt_parameters(n, r, p)
        salt = _b64d(kdf["salt"], maximum=SALT_BYTES)
        nonce = _b64d(cipher["nonce"], maximum=NONCE_BYTES)
        ciphertext = _b64d(cipher["ciphertext"], maximum=MAX_CIPHERTEXT_BYTES)
        if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES or len(ciphertext) < 16:
            raise VaultCryptoError("El archivo cifrado no es válido.")
        key = derive_key(
            passphrase,
            salt,
            n=n,
            r=r,
            p=p,
        )
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, AAD)
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise VaultCryptoError("Contenido del cofre no válido.")
        return decoded
    except VaultCryptoError:
        raise
    except (InvalidTag, KeyError, TypeError, ValueError, OverflowError, json.JSONDecodeError) as exc:
        raise VaultCryptoError("Contraseña incorrecta o cofre dañado.") from exc


def reencrypt_document(
    envelope: dict[str, Any], old_passphrase: str, new_passphrase: str
) -> dict[str, Any]:
    return encrypt_document(decrypt_document(envelope, old_passphrase), new_passphrase)
