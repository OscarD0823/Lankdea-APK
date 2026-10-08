import wave
from PIL import Image
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chest_visual_and_sounds_are_packaged():
    open_chest = ROOT / "assets" / "cofre_abierto_3d.png"
    assert open_chest.is_file()
    assert open_chest.stat().st_size > 100_000
    with Image.open(ROOT / "assets/cofre_atlas_gothic.png") as atlas:
        assert atlas.width == 2 * atlas.height
        assert atlas.mode == "RGBA"
        assert atlas.getchannel("A").getextrema() == (0, 255)
    assert (ROOT / "assets/licenses/LICENSE.txt").read_bytes() == (ROOT.parent / "LICENSE").read_bytes()
    assert (ROOT / "assets/licenses/THIRD-PARTY-NOTICES.txt").read_bytes() == (ROOT.parent / "THIRD-PARTY-NOTICES.txt").read_bytes()

    for name in ("chest_open.wav", "chest_close.wav"):
        path = ROOT / "assets" / "sounds" / name
        with wave.open(str(path), "rb") as audio:
            assert audio.getnchannels() == 1
            assert audio.getframerate() == 44_100
            assert audio.getnframes() > 22_000

    welcome = ROOT / "assets" / "sounds" / "assistant_welcome.wav"
    with wave.open(str(welcome), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 22_050
        assert audio.getnframes() > 100_000

    notice = ROOT / "assets" / "sounds" / "ASSISTANT_VOICE_NOTICE.txt"
    notice_text = notice.read_text(encoding="utf-8")
    assert "CC BY-SA 4.0" in notice_text
    assert "no requiere conexión a Internet" in notice_text
