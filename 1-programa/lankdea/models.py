from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .attachments import MAX_FILES, validate_metadata
from .crypto import VaultCryptoError


SCHEMA_VERSION = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_document(device: str = "unknown") -> dict[str, Any]:
    stamp = now_iso()
    return {
        "schema": SCHEMA_VERSION,
        "vault_id": str(uuid.uuid4()),
        "created_at": stamp,
        "updated_at": stamp,
        "updated_by": device,
        "revision": 0,
        "items": [],
        "settings": {
            "totp_enabled": False,
            "totp_secret": "",
            "sounds_enabled": True,
            "assistant_enabled": True,
            "animations_enabled": True,
            "ui_language": "es",
            "clipboard_clear_seconds": 15,
            "auto_lock_seconds": 300,
            "peer_enabled": False,
            "peer_code": "",
            "peer_host": "",
        },
    }


def normalize_item(item: dict[str, Any], device: str = "unknown") -> dict[str, Any]:
    stamp = str(item.get("updated_at") or item.get("created_at") or now_iso())
    item_type = item.get("type") if item.get("type") in ("password", "note", "file") else "note"
    normalized = {
        "id": str(item.get("id") or uuid.uuid4()),
        "type": item_type,
        "title": str(item.get("title") or ("Credencial" if item_type == "password" else "Nota")),
        "created_at": str(item.get("created_at") or stamp),
        "updated_at": stamp,
        "updated_by": str(item.get("updated_by") or device),
        "deleted_at": str(item.get("deleted_at") or ""),
    }
    if item_type == "password":
        normalized.update(
            service=str(item.get("service") or ""),
            username=str(item.get("username") or ""),
            password=str(item.get("password") or ""),
            notes=str(item.get("notes") or ""),
        )
    elif item_type == "file":
        normalized["attachment"] = validate_metadata(item.get("attachment"))
        normalized["title"] = str(item.get("title") or normalized["attachment"]["filename"])
        normalized["notes"] = str(item.get("notes") or "")
    else:
        normalized["content"] = str(item.get("content") or item.get("notes") or "")
    return normalized


def normalize_document(document: dict[str, Any], device: str = "unknown") -> dict[str, Any]:
    base = new_document(device)
    base.update({k: deepcopy(v) for k, v in document.items() if k != "items"})
    base["schema"] = SCHEMA_VERSION
    base["items"] = [normalize_item(item, device) for item in document.get("items", []) if isinstance(item, dict)]
    if sum(i["type"] == "file" and not i["deleted_at"] for i in base["items"]) > MAX_FILES:
        raise VaultCryptoError("El cofre admite hasta 128 archivos activos.")
    settings = {**new_document(device)["settings"], **dict(document.get("settings", {}))}
    # Retira únicamente preferencias de la antigua nube, no registros ni TOTP.
    settings.pop("cloud_email", None)
    settings.pop("cloud_rekey_pending", None)
    base["settings"] = settings
    return base


def new_item(item_type: str, device: str = "unknown", **values: Any) -> dict[str, Any]:
    stamp = now_iso()
    raw: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": item_type,
        "created_at": stamp,
        "updated_at": stamp,
        "updated_by": device,
        **values,
    }
    return normalize_item(raw, device)


def active_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(item) for item in document.get("items", []) if not item.get("deleted_at")]


def search_items(document: dict[str, Any], query: str) -> list[dict[str, Any]]:
    needle = query.casefold().strip()
    items = active_items(document)
    if not needle:
        return items
    return [item for item in items if needle in json.dumps(
        {key: value for key, value in item.items() if key != "attachment"} | (
            {"filename": item["attachment"]["filename"]} if item["type"] == "file" else {}
        ), ensure_ascii=False).casefold()]


def _winner(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def rank(item: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(item.get("updated_at") or item.get("deleted_at") or ""),
            str(item.get("updated_by") or ""),
            json.dumps(item, ensure_ascii=False, sort_keys=True),
        )

    return deepcopy(max((left, right), key=rank))


def merge_documents(
    local: dict[str, Any], remote: dict[str, Any], device: str = "unknown"
) -> tuple[dict[str, Any], dict[str, int]]:
    local = normalize_document(local, device)
    remote = normalize_document(remote, device)
    local_by_id = {item["id"]: item for item in local["items"]}
    remote_by_id = {item["id"]: item for item in remote["items"]}
    merged_items: list[dict[str, Any]] = []
    imported = 0
    kept_local = 0
    for item_id in sorted(set(local_by_id) | set(remote_by_id)):
        left = local_by_id.get(item_id)
        right = remote_by_id.get(item_id)
        if left is None:
            merged_items.append(deepcopy(right))
            imported += 1
        elif right is None:
            merged_items.append(deepcopy(left))
            kept_local += 1
        else:
            chosen = _winner(left, right)
            merged_items.append(chosen)
            if chosen == right and chosen != left:
                imported += 1
            elif chosen == left and chosen != right:
                kept_local += 1
    merged = deepcopy(local)
    merged["items"] = merged_items
    merged["revision"] = max(int(local.get("revision", 0)), int(remote.get("revision", 0))) + 1
    merged["updated_at"] = now_iso()
    merged["updated_by"] = device
    if not merged.get("vault_id"):
        merged["vault_id"] = remote.get("vault_id") or str(uuid.uuid4())
    return normalize_document(merged, device), {"imported": imported, "kept_local": kept_local}
