import json
from pathlib import Path

from lankdea.config import EditionConfig
from lankdea.models import active_items, new_document, new_item
from lankdea.storage import LocalVaultRepository

ROOT = Path(__file__).resolve().parents[1]


def test_old_edition_cannot_activate_removed_services(tmp_path):
    config = tmp_path / "edition.json"
    config.write_text(json.dumps({"edition": "firebase"}))
    assert EditionConfig.load(config).edition == "local"


def test_existing_vault_keeps_items_password_and_totp_without_rewriting_on_open(tmp_path):
    repo = LocalVaultRepository(tmp_path / "lankdea_vault_v2.json", "pc")
    document = new_document("pc")
    document["items"] = [new_item("note", title="Conservar", content="Contenido")]
    document["settings"].update(totp_enabled=True, totp_secret="EXISTINGSECRET")
    repo.create("misma contraseña maestra", document)
    original_bytes = repo.path.read_bytes()
    updated_app = LocalVaultRepository(repo.path, "pc")
    reopened = updated_app.unlock("misma contraseña maestra")
    assert active_items(reopened)[0]["content"] == "Contenido"
    assert reopened["settings"]["totp_secret"] == "EXISTINGSECRET"
    assert reopened["settings"]["totp_enabled"]
    assert repo.path.read_bytes() == original_bytes


def test_application_has_no_cloud_implementation():
    assert not (ROOT / "lankdea" / "firebase.py").exists()
    assert not (ROOT / "buildozer.firebase.spec").exists()
    ui = (ROOT / "lankdea" / "ui.py").read_text(encoding="utf-8")
    assert "Firebase" not in ui and "cloud_enabled" not in ui


def test_sensitive_ui_uses_memory_only_qr_masked_password_and_android_secure_flag():
    ui = (ROOT / "lankdea" / "ui.py").read_text(encoding="utf-8")
    assert 'qrcode.make(uri).save(qr_buffer, format="PNG")' in ui
    assert 'Image(texture=qr_texture)' in ui
    assert 'password=True, text=str(item.get("password", ""))' in ui
    assert "FLAG_SECURE" in ui


def test_responsive_chest_is_used_for_open_and_close_transitions():
    ui = (ROOT / "lankdea" / "ui.py").read_text(encoding="utf-8")
    assert "class ChestStage" in ui
    assert "class VaultBackdrop" in ui
    assert "class AssistantWelcome" in ui
    assert "class ResponsiveColumn" in ui
    assert "def _show_lock_transition" in ui
    assert "stage.chest.set_opened(" in ui
    chest = (ROOT / "lankdea" / "chest_3d.py").read_text(encoding="utf-8")
    assert "ChestVisual = Chest3D" in ui
    assert "cofre_atlas_gothic.png" in chest
    assert "@lru_cache(maxsize=1)" in chest
    assert "opening=1 if opened else 0" in chest
    assert "atlas.get_region" in chest
    assert "min_cell_width" in ui


def test_login_welcome_is_local_optional_and_does_not_expose_vault_data():
    ui = (ROOT / "lankdea" / "ui.py").read_text(encoding="utf-8")
    document = new_document("pc")

    assert document["settings"]["assistant_enabled"] is True
    assert "ASSISTANT_WELCOME_TEXT" in ui
    assert 'SoundLoader.load(str(asset("sounds/assistant_welcome.wav")))' in ui
    translations = (ROOT / "lankdea" / "i18n.py").read_text(encoding="utf-8")
    assert "IDENTIDAD VERIFICADA" in translations
    assert 'translate("identity_verified", language)' in ui
    assert "def toggle_assistant" in ui
    assert "Clock.schedule_once" in ui
    assert "Sus secretos" not in ui


def test_author_matches_github_identity_in_package_and_interface():
    ui = (ROOT / "lankdea" / "ui.py").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    installer = (
        ROOT.parent / "2-instaladores" / "configuracion-windows" / "Lankdea.iss"
    ).read_text(encoding="utf-8")

    assert "Autor: OscarD0823" in ui
    assert 'authors = [{name = "OscarD0823"}]' in project
    assert "AppPublisher=OscarD0823" in installer
