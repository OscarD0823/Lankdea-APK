from lankdea.models import active_items, merge_documents, new_document, new_item


def test_merge_keeps_newest_change_and_remote_addition():
    local = new_document("phone")
    shared = new_item("note", "phone", title="Compartida", content="local")
    shared["updated_at"] = "2026-01-01T10:00:00Z"
    local["items"] = [shared]

    remote = new_document("desktop")
    remote_shared = dict(shared, content="remota", updated_at="2026-01-01T11:00:00Z", updated_by="desktop")
    remote_only = new_item("password", "desktop", title="Correo", service="Correo", password="x")
    remote["items"] = [remote_shared, remote_only]

    merged, stats = merge_documents(local, remote, "phone")
    items = {item["id"]: item for item in active_items(merged)}
    assert items[shared["id"]]["content"] == "remota"
    assert remote_only["id"] in items
    assert stats["imported"] == 2


def test_newer_tombstone_wins_over_old_record():
    local = new_document("phone")
    item = new_item("note", "phone", title="Borrar", content="x")
    item["updated_at"] = "2026-01-01T10:00:00Z"
    local["items"] = [item]
    remote = new_document("desktop")
    deleted = dict(
        item,
        deleted_at="2026-01-01T12:00:00Z",
        updated_at="2026-01-01T12:00:00Z",
        updated_by="desktop",
    )
    remote["items"] = [deleted]
    merged, _ = merge_documents(local, remote, "phone")
    assert active_items(merged) == []
