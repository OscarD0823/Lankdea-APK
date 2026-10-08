from datetime import datetime, timezone

import pyotp

from lankdea.auth import master_password_error, verify_totp_code


def test_verify_totp_code_accepts_current_code_and_nearby_window():
    secret = pyotp.random_base32()
    moment = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    code = pyotp.TOTP(secret).at(moment)

    assert verify_totp_code(secret, code, for_time=moment)
    assert verify_totp_code(secret, code, for_time=moment.timestamp() + 30)


def test_verify_totp_code_rejects_invalid_or_malformed_values():
    secret = pyotp.random_base32()
    moment = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    valid_code = pyotp.TOTP(secret).at(moment)

    assert not verify_totp_code(secret, "12345", for_time=moment)
    assert not verify_totp_code(secret, "abcdef", for_time=moment)
    wrong_code = "000000" if valid_code != "000000" else "999999"
    assert not verify_totp_code(secret, wrong_code, for_time=moment)
    assert not verify_totp_code("clave-invalida", valid_code, for_time=moment)


def test_new_master_password_policy_rejects_short_common_and_repeated_values():
    assert master_password_error("muy corta")
    assert master_password_error("password1234")
    assert master_password_error("aaaaaaaaaaaa")
    assert not master_password_error("Cuatro palabras distintas 2026!")
