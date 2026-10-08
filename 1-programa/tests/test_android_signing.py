import pytest

from scripts.record_android import certificate_fingerprint

FINGERPRINT = "031f71a202e6ee4fb2ca07a82f610f90f577650a5fd1fcbc8b35419caef9fea6"


def output(label, subject="C=US, O=Android, CN=Android Debug", fingerprint=FINGERPRINT):
    return f"{label} certificate DN: {subject}\n{label} certificate SHA-256 digest: {fingerprint}\n"


@pytest.mark.parametrize("label", ["Signer #1", "V2 Signer:", "V3 Signer:", "V3.1 Signer:", "Signer (minSdkVersion=33, maxSdkVersion=2147483647)"])
def test_recognizes_sdk_36_and_37_certificate_labels(label):
    assert certificate_fingerprint(output(label), "debug") == FINGERPRINT


def test_multiple_schemes_with_same_certificate_are_valid():
    text = output("V2 Signer:") + output("V3 Signer:")
    assert certificate_fingerprint(text, "debug") == FINGERPRINT


def test_never_confuses_public_key_or_source_stamp_with_app_certificate():
    text = ("Signer #1 public key SHA-256 digest: " + FINGERPRINT + "\n"
            + output("Source Stamp Signer"))
    with pytest.raises(ValueError, match="certificado"):
        certificate_fingerprint(text, "debug")


def test_rejects_different_signers_and_missing_or_truncated_fingerprint():
    for text in (output("V2 Signer:") + output("V3 Signer:", fingerprint="a" * 64),
                 output("V2 Signer:", fingerprint="a" * 63), "", output("Unknown Signer")):
        with pytest.raises(ValueError):
            certificate_fingerprint(text, "debug")


def test_debug_is_still_rejected_for_publication():
    with pytest.raises(ValueError, match="canal"):
        certificate_fingerprint(output("V2 Signer:"), "release")
    assert certificate_fingerprint(output("V2 Signer:", subject="CN=Lankdea"), "release") == FINGERPRINT


def test_release_certificate_is_not_accepted_as_debug():
    with pytest.raises(ValueError, match="canal"):
        certificate_fingerprint(output("V2 Signer:", subject="CN=Lankdea"), "debug")
