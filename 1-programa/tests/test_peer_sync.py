import requests
import pytest

from lankdea.models import active_items, new_item
from lankdea.peer_sync import (
    PeerSyncClient,
    PeerSyncError,
    PeerSyncServer,
    MAX_RESPONSE_BODY,
    VAULT_PATH,
    adb_devices,
    auth_headers,
    generate_pair_code,
    normalize_pair_code,
    response_auth_headers,
    valid_pair_code,
)
from lankdea.storage import LocalVaultRepository


def test_pair_code_has_enough_entropy_and_normalizes():
    code = generate_pair_code()
    assert len(normalize_pair_code(code)) == 16
    assert normalize_pair_code(code.lower()) == normalize_pair_code(code)
    assert valid_pair_code(code)
    assert not valid_pair_code("0000-0000-0000-0000")


def test_pair_code_rejects_short_or_reduced_alphabet_values(tmp_path):
    repository = LocalVaultRepository(tmp_path / "mobile.json", "mobile")
    with pytest.raises(PeerSyncError, match="no es válido"):
        PeerSyncClient(repository, "123456")
    with pytest.raises(PeerSyncError, match="no es válido"):
        PeerSyncClient(repository, "0000-0000-0000-0000")


def test_adb_device_list_ignores_unauthorized_and_offline():
    output = "List of devices attached\nABC123\tdevice\nWAIT\tunauthorized\nOLD\toffline\n"
    assert adb_devices(output) == ["ABC123"]


def test_peer_server_merges_encrypted_vaults_and_rejects_replay(tmp_path):
    desktop = LocalVaultRepository(tmp_path / "desktop.json", "desktop")
    mobile = LocalVaultRepository(tmp_path / "mobile.json", "mobile")
    passphrase = "una contraseña compartida"
    desktop.create(passphrase)
    mobile.create(passphrase)
    desktop.upsert_item(new_item("note", "desktop", title="PC", content="uno"))
    mobile.upsert_item(new_item("note", "mobile", title="Móvil", content="dos"))
    code = generate_pair_code()
    server = PeerSyncServer(
        desktop, code, "desktop", host="127.0.0.1", port=0, broadcast=False
    )
    server.start()
    try:
        result = PeerSyncClient(mobile, code).sync("127.0.0.1", server.port)
        assert result["revision"] >= 1
        assert {item["title"] for item in active_items(desktop.snapshot())} == {"PC", "Móvil"}
        assert {item["title"] for item in active_items(mobile.snapshot())} == {"PC", "Móvil"}

        desktop_revision = desktop.snapshot()["revision"]
        mobile_revision = mobile.snapshot()["revision"]
        PeerSyncClient(mobile, code).sync("127.0.0.1", server.port)
        assert desktop.snapshot()["revision"] == desktop_revision
        assert mobile.snapshot()["revision"] == mobile_revision

        url = f"http://127.0.0.1:{server.port}{VAULT_PATH}"
        headers = auth_headers(code, "GET", VAULT_PATH)
        assert requests.get(url, headers=headers, timeout=2).status_code == 200
        assert requests.get(url, headers=headers, timeout=2).status_code == 401
        malformed = auth_headers(code, "GET", VAULT_PATH)
        malformed["X-Lankdea-Time"] = "9" * 400
        assert requests.get(url, headers=malformed, timeout=2).status_code == 401
    finally:
        server.stop()


class FakeResponse:
    def __init__(self, body=b"{}", *, headers=None, status=200):
        self.body = body
        self.headers = headers or {"Content-Length": str(len(body))}
        self.status_code = status
        self.ok = status < 400
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class FakeHTTP:
    def __init__(self, response):
        self.response = response

    def request(self, *args, **kwargs):
        assert kwargs["stream"] is True
        return self.response


def test_client_rejects_unsigned_response_before_json(tmp_path):
    repository = LocalVaultRepository(tmp_path / "mobile.json", "mobile")
    repository.create("una contraseña compartida")
    response = FakeResponse()
    client = PeerSyncClient(repository, generate_pair_code(), http=FakeHTTP(response))
    with pytest.raises(PeerSyncError, match="autenticar"):
        client._request("GET", "http://127.0.0.1:8765" + VAULT_PATH)
    assert response.closed


def test_response_signature_is_bound_to_request_and_rejects_replay(tmp_path):
    repository = LocalVaultRepository(tmp_path / "mobile.json", "mobile")
    repository.create("una contraseña compartida")
    code = generate_pair_code()
    client = PeerSyncClient(repository, code)
    request_nonce = auth_headers(code, "GET", VAULT_PATH)["X-Lankdea-Nonce"]
    body = b'{"ok":true}'
    headers = response_auth_headers(code, "GET", VAULT_PATH, 200, request_nonce, body)
    assert client._authorized_response("GET", VAULT_PATH, 200, request_nonce, headers, body)
    assert not client._authorized_response("GET", VAULT_PATH, 200, request_nonce, headers, body)
    malformed = dict(headers, **{"X-Lankdea-Response-Time": "9" * 400})
    assert not PeerSyncClient(repository, code)._authorized_response(
        "GET", VAULT_PATH, 200, request_nonce, malformed, body
    )
    other_request = auth_headers(code, "GET", VAULT_PATH)["X-Lankdea-Nonce"]
    assert not PeerSyncClient(repository, code)._authorized_response(
        "GET", VAULT_PATH, 200, other_request, headers, body
    )


def test_client_rejects_oversized_response_before_reading(tmp_path):
    repository = LocalVaultRepository(tmp_path / "mobile.json", "mobile")
    repository.create("una contraseña compartida")
    response = FakeResponse(headers={"Content-Length": str(MAX_RESPONSE_BODY + 1)})
    client = PeerSyncClient(repository, generate_pair_code(), http=FakeHTTP(response))
    with pytest.raises(PeerSyncError, match="grande"):
        client._request("GET", "http://127.0.0.1:8765" + VAULT_PATH)
    assert response.closed
