from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import requests

from .storage import MAX_ENVELOPE_FILE_BYTES, LocalVaultRepository
from .attachments import ID_PATTERN, MAX_CHUNK_BYTES


SERVICE = "lankdea-peer-v3"
STATUS_PATH = "/v3/status"
VAULT_PATH = "/v3/vault"
BLOB_PREFIX = "/v3/files/"
DEFAULT_PORT = 8765
DISCOVERY_PORT = 48765
MAX_BODY = MAX_ENVELOPE_FILE_BYTES + 64 * 1024
MAX_RESPONSE_BODY = MAX_BODY
MAX_CLOCK_SKEW = 120
MAX_ACTIVE_HANDLERS = 12
PAIR_CODE_PATTERN = re.compile(r"[A-Z2-7]{16}")
NONCE_PATTERN = re.compile(r"[0-9a-f]{24}")
TIMESTAMP_PATTERN = re.compile(r"[0-9]{10}")
SIGNATURE_PATTERN = re.compile(r"[0-9a-f]{64}")


class PeerSyncError(RuntimeError):
    pass


def find_adb(explicit: str | None = None) -> str | None:
    candidates = [explicit, shutil.which("adb")]
    for variable in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(variable)
        if sdk_root:
            candidates.append(str(Path(sdk_root) / "platform-tools" / "adb.exe"))
            candidates.append(str(Path(sdk_root) / "platform-tools" / "adb"))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            str(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
        )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    return None


def adb_devices(output: str) -> list[str]:
    return [
        line.split("\t", 1)[0].strip()
        for line in output.splitlines()
        if "\tdevice" in line and line.split("\t", 1)[0].strip()
    ]


class AdbReverseBridge:
    """Mantiene el puerto del PC visible como localhost en Android por USB/ADB."""

    def __init__(self, port: int = DEFAULT_PORT, *, adb_path: str | None = None) -> None:
        self.port = int(port)
        self.adb_path = find_adb(adb_path)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active_devices: tuple[str, ...] = ()
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.adb_path is not None

    @property
    def active_devices(self) -> tuple[str, ...]:
        with self._lock:
            return self._active_devices

    def start(self) -> None:
        if not self.available or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="lankdea-adb-reverse",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            self._active_devices = ()

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.adb_path), *arguments],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _loop(self) -> None:
        while not self._stop.is_set():
            connected: list[str] = []
            try:
                devices = adb_devices(self._run(["devices"]).stdout)
                for serial in devices:
                    result = self._run(
                        [
                            "-s",
                            serial,
                            "reverse",
                            f"tcp:{self.port}",
                            f"tcp:{self.port}",
                        ]
                    )
                    if result.returncode == 0:
                        connected.append(serial)
            except (OSError, subprocess.SubprocessError):
                connected = []
            with self._lock:
                self._active_devices = tuple(connected)
            self._stop.wait(6)


def generate_pair_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(10)).decode("ascii").rstrip("=")
    return "-".join(raw[index : index + 4] for index in range(0, len(raw), 4))


def normalize_pair_code(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def valid_pair_code(value: str) -> bool:
    return bool(PAIR_CODE_PATTERN.fullmatch(normalize_pair_code(value)))


def _pair_key(secret: str) -> bytes:
    normalized = normalize_pair_code(secret)
    if not valid_pair_code(normalized):
        raise PeerSyncError("El código de enlace no es válido.")
    return normalized.encode("ascii")


def _signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method.upper(), path, timestamp, nonce, digest)).encode("utf-8")
    return hmac.new(_pair_key(secret), canonical, hashlib.sha256).hexdigest()


def _response_signature(
    secret: str,
    method: str,
    path: str,
    status: int,
    request_nonce: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        (
            "response",
            method.upper(),
            path,
            str(int(status)),
            request_nonce,
            timestamp,
            nonce,
            digest,
        )
    ).encode("utf-8")
    return hmac.new(_pair_key(secret), canonical, hashlib.sha256).hexdigest()


def auth_headers(secret: str, method: str, path: str, body: bytes = b"") -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(12)
    return {
        "X-Lankdea-Time": timestamp,
        "X-Lankdea-Nonce": nonce,
        "X-Lankdea-Signature": _signature(secret, method, path, timestamp, nonce, body),
        "Content-Type": "application/json",
    }


def response_auth_headers(
    secret: str,
    method: str,
    path: str,
    status: int,
    request_nonce: str,
    body: bytes,
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(12)
    return {
        "X-Lankdea-Response-Time": timestamp,
        "X-Lankdea-Response-Nonce": nonce,
        "X-Lankdea-Response-Signature": _response_signature(
            secret,
            method,
            path,
            status,
            request_nonce,
            timestamp,
            nonce,
            body,
        ),
    }


class _NonceWindow:
    def __init__(self, limit: int = 512) -> None:
        self._values: set[str] = set()
        self._order: deque[str] = deque()
        self._limit = limit
        self._lock = threading.Lock()

    def take(self, nonce: str) -> bool:
        with self._lock:
            if not NONCE_PATTERN.fullmatch(nonce) or nonce in self._values:
                return False
            self._values.add(nonce)
            self._order.append(nonce)
            while len(self._order) > self._limit:
                self._values.discard(self._order.popleft())
            return True


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(
        self,
        address: tuple[str, int],
        repository: LocalVaultRepository,
        secret: str,
        device: str,
        on_update: Callable[[dict[str, int]], None] | None,
    ) -> None:
        super().__init__(address, _Handler)
        self.repository = repository
        self.secret = normalize_pair_code(secret)
        self.device = device
        self.on_update = on_update
        self.nonces = _NonceWindow()
        self._handler_slots = threading.BoundedSemaphore(MAX_ACTIVE_HANDLERS)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        """Rechaza conexiones sobrantes antes de crear otro hilo."""
        if not self._handler_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._handler_slots.release()
            raise

    def process_request_thread(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._handler_slots.release()


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(6)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response_headers = response_auth_headers(
            self.server.secret,
            self.command,
            self.path,
            status,
            self.headers.get("X-Lankdea-Nonce", ""),
            body,
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in response_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise PeerSyncError("Tamaño de solicitud inválido.") from exc
        if length < 0 or length > MAX_BODY:
            raise PeerSyncError("La solicitud es demasiado grande.")
        body = self.rfile.read(length)
        if len(body) != length:
            raise PeerSyncError("La solicitud quedó incompleta.")
        return body

    def _auth_headers_well_formed(self) -> bool:
        timestamp = self.headers.get("X-Lankdea-Time", "")
        nonce = self.headers.get("X-Lankdea-Nonce", "")
        signature = self.headers.get("X-Lankdea-Signature", "")
        if not (
            TIMESTAMP_PATTERN.fullmatch(timestamp)
            and NONCE_PATTERN.fullmatch(nonce)
            and SIGNATURE_PATTERN.fullmatch(signature)
        ):
            return False
        try:
            return abs(time.time() - int(timestamp)) <= MAX_CLOCK_SKEW
        except (ValueError, OverflowError):
            return False

    def _authorized(self, body: bytes) -> bool:
        timestamp = self.headers.get("X-Lankdea-Time", "")
        nonce = self.headers.get("X-Lankdea-Nonce", "")
        received = self.headers.get("X-Lankdea-Signature", "")
        if not (
            TIMESTAMP_PATTERN.fullmatch(timestamp)
            and NONCE_PATTERN.fullmatch(nonce)
            and SIGNATURE_PATTERN.fullmatch(received)
        ):
            return False
        try:
            fresh = abs(time.time() - int(timestamp)) <= MAX_CLOCK_SKEW
        except (ValueError, OverflowError):
            fresh = False
        expected = _signature(
            self.server.secret, self.command, self.path, timestamp, nonce, body
        )
        return (
            fresh
            and hmac.compare_digest(received, expected)
            and self.server.nonces.take(nonce)
        )

    def do_GET(self) -> None:  # noqa: N802
        if self.path == STATUS_PATH:
            self._send(200, {"service": SERVICE})
            return
        blob = _blob_address(self.path)
        if self.path != VAULT_PATH and blob is None:
            self._send(404, {"error": "not-found"})
            return
        if not self._authorized(b""):
            self._send(401, {"error": "pairing-required"})
            return
        try:
            if blob is not None:
                try:
                    encrypted = self.server.repository.read_attachment_chunk(*blob)
                except FileNotFoundError:
                    self._send(404, {"error": "chunk-missing"})
                    return
                self._send(200, {"ok": True} if self.path.endswith("?check=1") else {"chunk": base64.b64encode(encrypted).decode("ascii")})
                return
            envelope = self.server.repository.read_envelope()
            revision = int(self.server.repository.snapshot().get("revision", 0))
        except Exception:
            self._send(423, {"error": "vault-unavailable"})
            return
        self._send(200, {"envelope": envelope, "revision": revision})

    def do_POST(self) -> None:  # noqa: N802
        blob = _blob_address(self.path)
        if self.path != VAULT_PATH and blob is None:
            self._send(404, {"error": "not-found"})
            return
        if not self._auth_headers_well_formed():
            self._send(401, {"error": "pairing-required"})
            return
        try:
            body = self._body()
        except PeerSyncError as exc:
            self._send(413, {"error": str(exc)})
            return
        if not self._authorized(body):
            self._send(401, {"error": "pairing-required"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
            if blob is not None:
                encoded = payload["chunk"]
                if not isinstance(encoded, str) or len(encoded) > ((MAX_CHUNK_BYTES + 2) // 3) * 4:
                    raise ValueError("chunk")
                encrypted = base64.b64decode(encoded, validate=True)
                self.server.repository.receive_attachment_chunk(*blob, encrypted)
                self._send(200, {"ok": True})
                return
            envelope = payload["envelope"]
            if not isinstance(envelope, dict):
                raise ValueError("envelope")
            stats = self.server.repository.merge_envelope(envelope)
            merged = self.server.repository.read_envelope()
            revision = int(self.server.repository.snapshot().get("revision", 0))
        except Exception:
            self._send(400, {"error": "invalid-encrypted-vault"})
            return
        if self.server.on_update:
            self.server.on_update(stats)
        self._send(200, {"envelope": merged, "revision": revision, "stats": stats})


class PeerSyncServer:
    def __init__(
        self,
        repository: LocalVaultRepository,
        secret: str,
        device: str,
        *,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        on_update: Callable[[dict[str, int]], None] | None = None,
        broadcast: bool = True,
    ) -> None:
        if not valid_pair_code(secret):
            raise PeerSyncError("El código de enlace no es válido.")
        self._server = _Server((host, port), repository, secret, device, on_update)
        self._thread: threading.Thread | None = None
        self._beacon: threading.Thread | None = None
        self._stop = threading.Event()
        self.broadcast = broadcast

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="lankdea-peer-server", daemon=True
        )
        self._thread.start()
        if self.broadcast:
            self._beacon = threading.Thread(
                target=self._broadcast_loop, name="lankdea-peer-beacon", daemon=True
            )
            self._beacon.start()

    def stop(self) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def _broadcast_loop(self) -> None:
        packet = json.dumps(
            {"service": SERVICE, "port": self.port},
            separators=(",", ":"),
        ).encode("utf-8")
        while not self._stop.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as beacon:
                    beacon.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    beacon.sendto(packet, ("255.255.255.255", DISCOVERY_PORT))
            except OSError:
                pass
            self._stop.wait(3)


def discover_peer(timeout: float = 1.2) -> tuple[str, int] | None:
    deadline = time.monotonic() + timeout
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("", DISCOVERY_PORT))
            while time.monotonic() < deadline:
                listener.settimeout(max(0.05, deadline - time.monotonic()))
                data, address = listener.recvfrom(2048)
                payload = json.loads(data.decode("utf-8"))
                if payload.get("service") == SERVICE:
                    return address[0], int(payload.get("port", DEFAULT_PORT))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return None


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


class PeerSyncClient:
    def __init__(
        self,
        repository: LocalVaultRepository,
        secret: str,
        *,
        timeout: float = 4,
        http: requests.Session | None = None,
    ) -> None:
        if not valid_pair_code(secret):
            raise PeerSyncError("El código de enlace no es válido.")
        self.repository = repository
        self.secret = secret
        self.timeout = timeout
        self.http = http or requests.Session()
        self.nonces = _NonceWindow()

    def sync(self, host: str, port: int = DEFAULT_PORT) -> dict[str, Any]:
        base = f"http://{host}:{int(port)}"
        remote = self._request("GET", base + VAULT_PATH)
        stats = self.repository.merge_envelope(remote["envelope"])
        body = json.dumps(
            {"envelope": self.repository.read_envelope()},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        merged = self._request("POST", base + VAULT_PATH, body)
        final_stats = self.repository.merge_envelope(merged["envelope"])
        transferred = 0
        missing = 0
        # Un bloque verificado puede reusarse tras una desconexión. Solo se
        # transfieren archivos referenciados en los metadatos del cofre abierto.
        for item in self.repository.snapshot()["items"]:
            if item["type"] != "file" or item.get("deleted_at"):
                continue
            metadata = item["attachment"]
            for index in range(len(metadata["hashes"])):
                self.repository.attachment_metadata(metadata["file_id"])
                path = f"{BLOB_PREFIX}{metadata['file_id']}/{index}"
                try:
                    local = self.repository.read_attachment_chunk(metadata["file_id"], index)
                except FileNotFoundError:
                    local = None
                remote_chunk = self._request("GET", base + path + ("?check=1" if local is not None else ""), allow_missing=True)
                if remote_chunk.get("error") == "chunk-missing":
                    if local is None:
                        missing += 1
                        continue
                    body = json.dumps({"chunk": base64.b64encode(local).decode("ascii")}).encode("ascii")
                    self._request("POST", base + path, body)
                    transferred += 1
                elif local is None:
                    encoded = remote_chunk.get("chunk")
                    if not isinstance(encoded, str) or len(encoded) > ((MAX_CHUNK_BYTES + 2) // 3) * 4:
                        raise PeerSyncError("El PC respondió con un bloque inválido.")
                    self.repository.receive_attachment_chunk(metadata["file_id"], index, base64.b64decode(encoded, validate=True))
                    transferred += 1
        return {
            "host": host,
            "port": int(port),
            "imported": stats["imported"] + final_stats["imported"],
            "kept_local": stats["kept_local"] + final_stats["kept_local"],
            "revision": int(merged.get("revision", 0)),
            "blocks_transferred": transferred,
            "blocks_missing": missing,
        }

    def _request(self, method: str, url: str, body: bytes = b"", *, allow_missing=False) -> dict[str, Any]:
        path = "/" + url.split("/", 3)[-1]
        headers = auth_headers(self.secret, method, path, body)
        request_nonce = headers["X-Lankdea-Nonce"]
        try:
            response = self.http.request(
                method,
                url,
                data=body if body else None,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )
        except requests.RequestException as exc:
            raise PeerSyncError("No se encontró el cofre del PC.") from exc
        try:
            response_body = self._read_response(response)
            if not self._authorized_response(
                method, path, response.status_code, request_nonce, response.headers, response_body
            ):
                raise PeerSyncError("No se pudo autenticar la respuesta del PC.")
            payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PeerSyncError("El PC respondió con un formato inválido.") from exc
        finally:
            response.close()
        if not isinstance(payload, dict):
            raise PeerSyncError("El PC respondió con un formato inválido.")
        if allow_missing and response.status_code == 404 and payload.get("error") == "chunk-missing":
            return payload
        if not response.ok:
            message = payload.get("error", "No se pudo sincronizar con el PC.")
            if response.status_code == 401:
                message = "El código de enlace no coincide con el del PC."
            raise PeerSyncError(str(message))
        return payload

    @staticmethod
    def _read_response(response: requests.Response) -> bytes:
        content_length = response.headers.get("Content-Length", "")
        if content_length:
            try:
                if int(content_length) < 0 or int(content_length) > MAX_RESPONSE_BODY:
                    raise PeerSyncError("La respuesta del PC es demasiado grande.")
            except ValueError as exc:
                raise PeerSyncError("El PC respondió con un tamaño inválido.") from exc
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_RESPONSE_BODY:
                raise PeerSyncError("La respuesta del PC es demasiado grande.")
            chunks.append(chunk)
        return b"".join(chunks)

    def _authorized_response(
        self,
        method: str,
        path: str,
        status: int,
        request_nonce: str,
        headers: Any,
        body: bytes,
    ) -> bool:
        timestamp = headers.get("X-Lankdea-Response-Time", "")
        nonce = headers.get("X-Lankdea-Response-Nonce", "")
        received = headers.get("X-Lankdea-Response-Signature", "")
        if not (
            TIMESTAMP_PATTERN.fullmatch(timestamp)
            and NONCE_PATTERN.fullmatch(nonce)
            and SIGNATURE_PATTERN.fullmatch(received)
        ):
            return False
        try:
            fresh = abs(time.time() - int(timestamp)) <= MAX_CLOCK_SKEW
        except (ValueError, OverflowError):
            fresh = False
        expected = _response_signature(
            self.secret,
            method,
            path,
            status,
            request_nonce,
            timestamp,
            nonce,
            body,
        )
        return (
            fresh
            and hmac.compare_digest(received, expected)
            and self.nonces.take(nonce)
        )


def split_host(value: str, default_port: int = DEFAULT_PORT) -> tuple[str, int]:
    candidate = value.strip().replace("http://", "").replace("https://", "").rstrip("/")
    if not candidate:
        return "", default_port
    if ":" not in candidate:
        return candidate, default_port
    host, port = candidate.rsplit(":", 1)
    try:
        return host.strip(), int(port)
    except ValueError as exc:
        raise PeerSyncError("El puerto del PC no es válido.") from exc


def _blob_address(path: str) -> tuple[str, int] | None:
    if "?" in path:
        if not path.endswith("?check=1"):
            return None
        path = path[:-8]
    if not path.startswith(BLOB_PREFIX):
        return None
    parts = path[len(BLOB_PREFIX):].split("/")
    if len(parts) != 2 or not ID_PATTERN.fullmatch(parts[0]) or not re.fullmatch(r"0|[1-9][0-9]{0,2}", parts[1]):
        return None
    index = int(parts[1])
    return (parts[0], index) if index < 128 else None
