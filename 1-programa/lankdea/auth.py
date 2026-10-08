"""Ayudas de autenticación independientes de la interfaz gráfica."""

from __future__ import annotations

from datetime import datetime

import pyotp


MIN_MASTER_PASSWORD_LENGTH = 12
MAX_MASTER_PASSWORD_LENGTH = 1024
COMMON_MASTER_PASSWORDS = {
    "123456789012",
    "contrasena123",
    "contraseña123",
    "lankdea12345",
    "password1234",
    "qwerty123456",
}


def master_password_error(value: str) -> str:
    """Valida nuevas contraseñas sin cambiar las ya existentes al desbloquear."""

    if not isinstance(value, str):
        return "La contraseña maestra no es válida."
    if len(value) < MIN_MASTER_PASSWORD_LENGTH:
        return f"Usa al menos {MIN_MASTER_PASSWORD_LENGTH} caracteres."
    if len(value) > MAX_MASTER_PASSWORD_LENGTH:
        return "La contraseña maestra es demasiado larga."
    folded = value.casefold().strip()
    if folded in COMMON_MASTER_PASSWORDS or len(set(folded)) < 4:
        return "Evita contraseñas comunes, secuencias y caracteres repetidos."
    return ""


def verify_totp_code(
    secret: str,
    code: str,
    *,
    for_time: datetime | int | float | None = None,
    valid_window: int = 1,
) -> bool:
    """Valida un código TOTP de seis dígitos sin aceptar entradas ambiguas."""

    clean_code = code.strip()
    if len(clean_code) != 6 or not clean_code.isdigit() or not secret.strip():
        return False

    try:
        totp = pyotp.TOTP(secret.strip())
        if for_time is None:
            return bool(totp.verify(clean_code, valid_window=valid_window))
        return bool(
            totp.verify(clean_code, for_time=for_time, valid_window=valid_window)
        )
    except (TypeError, ValueError):
        return False
