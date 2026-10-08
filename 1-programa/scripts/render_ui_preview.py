"""Control visual reproducible con datos ficticios; excluido de los builds."""
from __future__ import annotations

import os
import argparse
from io import BytesIO
from pathlib import Path

os.environ["LANKDEA_DATA_DIR"] = str(Path(__file__).resolve().parents[2] / ".preview-data")
os.environ["KIVY_METRICS_DENSITY"] = "1"
os.environ["KIVY_DPI"] = "96"
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_NO_CONFIG"] = "1"

from kivy.config import Config

# Las capturas no requieren entrada nativa; una ventana SDL oculta no tiene
# HWND activo para los proveedores wm_pen/wm_touch de Windows.
for provider, _value in list(Config.items("input")):
    Config.remove_option("input", provider)

from kivy.clock import Clock
from kivy.core.window import Window

from lankdea.ui import LankdeaApp
from lankdea.models import new_item


OUTPUT = Path(__file__).resolve().parents[2] / ".preview"
OUTPUT.mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--width", type=int, default=1000)
parser.add_argument("--height", type=int, default=760)
parser.add_argument("--main", action="store_true")
parser.add_argument("--language", default="es")
parser.add_argument("--hidden", action="store_true", help="Renderizar sin mostrar la ventana SDL")
args = parser.parse_args()
Window.size = (args.width, args.height)
if args.hidden:
    Window.hide()

app = LankdeaApp()
def schedule_previews(_dt):
    if args.main:
        app.startup_intro._done = True
        app.app_root.remove_widget(app.startup_intro)
        if app.repository.exists:
            app.repository.unlock("DEMO ONLY - no real secrets")
        else:
            app.repository.create("DEMO ONLY - no real secrets")
            app.repository.upsert_item(new_item("note", "demo", title="Mi primera nota", content="Datos ficticios para comprobar el diseño."))
            app.repository.upsert_item(new_item("password", "demo", title="Correo de ejemplo", service="Ejemplo", username="demo@example.invalid", password="ficticio"))
            app.repository.import_attachment(BytesIO(b"Demo document"), name="Documento-de-ejemplo.pdf", size=13)
        app.language = args.language
        app.show_main()
        Clock.schedule_once(lambda _dt: app.app_root.export_to_png(str(OUTPUT / f"main-{args.width}x{args.height}-{args.language}.png")), 1.2)
        Clock.schedule_once(lambda _dt: app.stop(), 1.5)
        return
    app.language = args.language
    app.show_unlock()
    Clock.schedule_once(lambda _dt: app.app_root.export_to_png(str(OUTPUT / f"intro-{args.width}x{args.height}.png")), 1.25)
    Clock.schedule_once(lambda _dt: app.app_root.export_to_png(str(OUTPUT / f"login-{args.width}x{args.height}-{args.language}.png")), 4.2)
    Clock.schedule_once(lambda _dt: app.stop(), 4.5)
Clock.schedule_once(schedule_previews, 0)
app.run()
