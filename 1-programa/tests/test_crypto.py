import copy

import pytest

from lankdea.crypto import VaultCryptoError, decrypt_document, encrypt_document
from lankdea.models import new_document


def test_round_trip_keeps_unicode():
    document = new_document("test")
    document["items"] = [{"id": "1", "type": "note", "title": "Tesoro", "content": "Cañón 💜"}]
    envelope = encrypt_document(document, "una contraseña suficientemente larga")
    assert decrypt_document(envelope, "una contraseña suficientemente larga") == document
    assert "Tesoro" not in envelope["cipher"]["ciphertext"]


def test_wrong_password_is_rejected():
    envelope = encrypt_document(new_document("test"), "contraseña correcta")
    with pytest.raises(VaultCryptoError):
        decrypt_document(envelope, "contraseña equivocada")


def test_tampering_is_detected():
    envelope = encrypt_document(new_document("test"), "contraseña correcta")
    damaged = copy.deepcopy(envelope)
    value = damaged["cipher"]["ciphertext"]
    damaged["cipher"]["ciphertext"] = ("A" if value[0] != "A" else "B") + value[1:]
    with pytest.raises(VaultCryptoError):
        decrypt_document(damaged, "contraseña correcta")


@pytest.mark.parametrize(
    "field,value",
    [
        ("n", 2**30),
        ("n", "32768"),
        ("n", True),
        ("r", 1000),
        ("p", 1000),
    ],
)
def test_untrusted_scrypt_parameters_are_bounded_before_derivation(field, value):
    envelope = encrypt_document(new_document("test"), "contraseña correcta")
    envelope["kdf"][field] = value
    with pytest.raises(VaultCryptoError, match="Parámetros"):
        decrypt_document(envelope, "contraseña correcta")


@pytest.mark.parametrize(
    "field,value",
    [
        ("salt", "%%%"),
        ("nonce", "QQ=="),
        ("ciphertext", "QQ=="),
    ],
)
def test_malformed_or_wrong_length_binary_fields_are_rejected(field, value):
    envelope = encrypt_document(new_document("test"), "contraseña correcta")
    target = envelope["kdf"] if field == "salt" else envelope["cipher"]
    target[field] = value
    with pytest.raises(VaultCryptoError):
        decrypt_document(envelope, "contraseña correcta")
