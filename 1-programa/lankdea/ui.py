from __future__ import annotations

import os
import secrets
import socket
import threading
import time
import webbrowser
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import pyotp

try:
    import qrcode
except Exception:  # pragma: no cover - opcional en escritorio mínimo
    qrcode = None

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.audio import SoundLoader
from kivy.core.image import Image as CoreImage
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import Metrics, dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

from . import __version__
from .auth import master_password_error, verify_totp_code
from .config import EditionConfig, resource_root
from .crypto import VaultCryptoError
from .i18n import LANGUAGES, language_name, normalize_language, translate
from .models import active_items, new_item, search_items
from .file_access import android_pick, open_selected, selected_details
from .attachments import safe_filename
from .chest_3d import Chest3D
from .peer_sync import (
    AdbReverseBridge,
    DEFAULT_PORT,
    PeerSyncClient,
    PeerSyncError,
    PeerSyncServer,
    discover_peer,
    generate_pair_code,
    local_ip,
    normalize_pair_code,
    split_host,
    valid_pair_code,
)
from .storage import LocalVaultRepository, migrate_legacy_file, retire_legacy_artifacts
from .updates import RELEASES_URL, check_latest_release


BG = (0.018, 0.008, 0.030, 1)
PANEL = (0.055, 0.025, 0.082, 0.98)
PANEL_LIGHT = (0.095, 0.047, 0.13, 0.98)
PURPLE = (0.48, 0.19, 0.72, 1)
PURPLE_DARK = (0.14, 0.065, 0.21, 1)
MAGENTA = (0.92, 0.28, 0.48, 1)
GOLD = (0.94, 0.72, 0.35, 1)
TEXT = (0.96, 0.93, 1.0, 1)
MUTED = (0.72, 0.66, 0.79, 1)
GOOD = (0.42, 0.88, 0.63, 1)
DANGER = (0.88, 0.25, 0.38, 1)

ASSISTANT_WELCOME_TEXT = (
    "Bienvenido a Lankdea. Identidad verificada. El relicario está abierto y todos "
    "los sistemas de protección están activos. Todo está listo."
)


def asset(name: str) -> Path:
    return resource_root() / "assets" / name


FONT_FILE = asset("fonts/NotoSansCJKsc-Regular.otf")
if FONT_FILE.is_file():
    # La misma familia soporta letras latinas, cirílicas y CJK, también en APK.
    LabelBase.register(name="Roboto", fn_regular=str(FONT_FILE), fn_bold=str(FONT_FILE),
                       fn_italic=str(FONT_FILE), fn_bolditalic=str(FONT_FILE))


class Card(BoxLayout):
    def __init__(self, *, color=PANEL, border=(0.61, 0.38, 0.75, 0.55), radius=16, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            self._fill_color = Color(*color)
            self._background = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
            self._line_color = Color(*border)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(radius)), width=1.05
            )
            Color(*GOLD[:3], .56)
            self._corners = [Line(points=(), width=1.2) for _ in range(4)]
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(self._radius))
        length, inset = min(dp(18), self.width / 8, self.height / 5), dp(8)
        for line, (x, y, sx, sy) in zip(self._corners, (
            (self.x + inset, self.y + inset, 1, 1),
            (self.x + self.width - inset, self.y + inset, -1, 1),
            (self.x + inset, self.y + self.height - inset, 1, -1),
            (self.x + self.width - inset, self.y + self.height - inset, -1, -1),
        )):
            line.points = (x, y + sy * length, x, y, x + sx * length, y)


class VaultButton(Button):
    def __init__(self, *, accent=False, danger=False, compact=False, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT
        self.bold = True
        self.font_size = dp(12 if compact else 13)
        self.size_hint_y = None
        self.height = dp(42 if compact else 50)
        self._normal = DANGER if danger else (PURPLE if accent else PURPLE_DARK)
        self._down = tuple(min(1, c * 1.18) for c in self._normal[:3]) + (1,)
        with self.canvas.before:
            self._button_color = Color(*self._normal)
            self._button_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*GOLD[:3], .68 if accent else .23)
            self._button_edge = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(12)), width=1)
        self.bind(pos=self._update_button, size=self._update_button, state=self._state_changed)
        self.bind(width=self._fit_text)

    def _update_button(self, *_):
        self._button_bg.pos = self.pos
        self._button_bg.size = self.size
        self._button_edge.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(12))

    def _state_changed(self, *_):
        self._button_color.rgba = self._down if self.state == "down" else self._normal

    def _fit_text(self, *_):
        self.font_size = dp(10 if self.width < dp(95) else (11 if self.width < dp(125) else 12))


class AdaptiveGrid(GridLayout):
    def __init__(self, *, item_count: int, row_height=50, min_cell_width=145, **kwargs):
        super().__init__(**kwargs)
        self.item_count = item_count
        self.row_height = row_height
        self.min_cell_width = min_cell_width
        self.size_hint_y = None
        self.bind(width=self._adapt)
        Clock.schedule_once(self._adapt, 0)

    def _adapt(self, *_):
        spacing_x = self.spacing[0] if isinstance(self.spacing, (list, tuple)) else self.spacing
        usable = max(0, self.width + spacing_x)
        columns = max(1, int(usable // (dp(self.min_cell_width) + spacing_x)))
        self.cols = max(1, min(6, self.item_count, columns))
        rows = max(1, (self.item_count + self.cols - 1) // self.cols)
        spacing_y = self.spacing[1] if isinstance(self.spacing, (list, tuple)) else self.spacing
        self.height = dp(rows * self.row_height) + max(0, rows - 1) * spacing_y


class ResponsiveColumn(BoxLayout):
    """Centra el contenido y limita su ancho sin romper el desplazamiento móvil."""

    def __init__(self, *, max_content_width=720, **kwargs):
        super().__init__(**kwargs)
        self.max_content_width = max_content_width
        self.bind(width=self._adapt_padding)
        Clock.schedule_once(self._adapt_padding, 0)

    def add_widget(self, widget, *args, **kwargs):
        result = super().add_widget(widget, *args, **kwargs)
        widget.bind(height=self._queue_layout)
        self._queue_layout()
        return result

    def _adapt_padding(self, *_):
        vertical = dp(12)
        side = max(dp(10), (self.width - dp(self.max_content_width)) / 2)
        self.padding = (side, vertical, side, dp(20))
        self._run_layout()
        self._queue_layout()

    def _queue_layout(self, *_):
        Clock.unschedule(self._run_layout)
        Clock.schedule_once(self._run_layout, 0)

    def _run_layout(self, *_):
        self.do_layout()
        left, _top, right, _bottom = self.padding
        content_width = max(0, self.width - left - right)
        for child in self.children:
            if child.size_hint_x is not None:
                child.width = content_width
            layout = getattr(child, "do_layout", None)
            if callable(layout):
                layout()
        self.do_layout()


class VaultBackdrop(FloatLayout):
    """Fondo oscuro que reutiliza el arte oficial sin competir con el formulario."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.banner = Image(
            source=str(asset("cofre_banner.png")),
            fit_mode="cover",
            color=(0.66, 0.30, 0.85, 0.16),
        )
        self.add_widget(self.banner)

    def add_widget(self, widget, *args, **kwargs):
        # Ambos planos deben cubrir el área completa. La asignación explícita
        # también evita el lienzo inicial de 100 px observado con SDL/Windows.
        widget.size_hint = (None, None)
        widget.pos = self.pos
        widget.size = self.size
        self.bind(pos=widget.setter("pos"), size=widget.setter("size"))
        return super().add_widget(widget, *args, **kwargs)


class AssistantWelcome(Card):
    """Confirmación visual breve después de una autenticación correcta."""

    def __init__(self, *, language="es", **kwargs):
        self.language = language
        super().__init__(
            orientation="vertical",
            padding=(dp(14), dp(9)),
            spacing=dp(1),
            size_hint_y=None,
            height=0,
            opacity=0,
            color=(0.025, 0.035, 0.075, 0.98),
            border=(0.70, 0.39, 0.92, 0.82),
            radius=14,
            **kwargs,
        )
        self._target_height = dp(92)
        self._dismiss_event = None
        self._present_event = None
        self._animation = None
        self.status = make_label(
            translate("identity_verified", language),
            10,
            GOLD,
            True,
            22,
        )
        self.message = make_label(
            translate("welcome_message", language),
            12,
            TEXT,
            False,
            54,
        )
        self.add_widget(self.status)
        self.add_widget(self.message)
        self.bind(width=self._adapt)

    def _adapt(self, *_):
        narrow = self.width <= dp(480)
        self._target_height = dp(98 if narrow else 92)
        self.status.text = translate("identity_verified", self.language)
        self.status.font_size = dp(9 if narrow else 10)
        self.status.height = dp(22)
        self.message.font_size = dp(11 if narrow else 12)
        self.message.height = dp(54)

    def present(self, *_):
        self._present_event = None
        self._adapt()
        Animation.cancel_all(self)
        if self._dismiss_event is not None:
            self._dismiss_event.cancel()
        self._animation = Animation(
            opacity=1,
            height=self._target_height,
            duration=0.34,
            t="out_cubic",
        )
        self._animation.start(self)
        self._dismiss_event = Clock.schedule_once(self.dismiss, 6.4)

    def dismiss(self, *_):
        self._dismiss_event = None
        self._animation = Animation(opacity=0, height=0, duration=0.42, t="in_cubic")
        self._animation.bind(
            on_complete=lambda *_: self.parent.remove_widget(self)
            if self.parent is not None
            else None
        )
        self._animation.start(self)




ChestVisual = Chest3D


class ChestStage(Card):
    """Escenario principal del cofre para entrar y para bloquear."""

    def __init__(self, *, opened=False, caption="TU COFRE CIFRADO", **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(8),
            spacing=dp(2),
            size_hint_y=None,
            color=(0.035, 0.014, 0.057, 1),
            border=(0.70, 0.46, 0.31, 0.78),
            **kwargs,
        )
        self.caption = make_label(caption, 12, GOLD, True, 24)
        self.caption.halign = "center"
        self.chest = ChestVisual(opened=opened)
        self.add_widget(self.caption)
        self.add_widget(self.chest)
        self.bind(width=self._adapt)
        Window.bind(size=self._adapt)
        Clock.schedule_once(self._adapt, 0)

    def _adapt(self, *_):
        if self.width < dp(380):
            self.height = dp(306)
            self.caption.font_size = dp(10)
        elif self.width < dp(620):
            self.height = dp(358)
            self.caption.font_size = dp(11)
        else:
            self.height = dp(424)
            self.caption.font_size = dp(12)
        self.height = min(self.height, max(dp(150), Window.height * .46))
        self.do_layout()


class HeroBanner(Card):
    def __init__(self, edition: EditionConfig, **kwargs):
        super().__init__(
            orientation="horizontal",
            padding=dp(14),
            spacing=dp(12),
            color=(0.045, 0.018, 0.070, 1),
            border=(0.70, 0.46, 0.31, 0.72),
            **kwargs,
        )
        self.size_hint_y = None
        self.height = dp(130)
        self.content = BoxLayout(orientation="vertical", spacing=dp(4))
        self.title_label = make_label("LANKDEA", 27, TEXT, True, 38)
        self.subtitle_label = make_label("Relicario cifrado personal", 14, MUTED, False, 25)
        self.content.add_widget(self.title_label)
        self.content.add_widget(self.subtitle_label)
        self.badge_label = make_label("OSCARD0823  •  LOCAL", 11, GOLD, True, 23)
        self.content.add_widget(self.badge_label)
        self.add_widget(self.content)
        self.chest = ChestVisual(opened=True, size_hint_x=None, width=dp(120))
        self.add_widget(self.chest)
        self.bind(width=self._adapt)

    def _adapt(self, *_):
        self.adapt_to_view(self.width, Window.height)

    def adapt_to_view(self, width: float, height: float):
        narrow = width <= dp(480)
        short = height <= dp(500)
        self.height = dp(102 if short else (148 if narrow else 180))
        self.chest.width = dp(78 if short else (118 if narrow else 160))
        self.title_label.font_size = dp(19 if short else (22 if narrow else 27))
        self.subtitle_label.font_size = dp(10 if short else (11 if narrow else 14))
        self.subtitle_label.height = dp(0 if short else 25)
        self.subtitle_label.opacity = 0 if short else 1
        self.badge_label.font_size = dp(9 if short or narrow else 11)


def make_label(text: str, size=13, color=TEXT, bold=False, height=30, *, markup=False) -> Label:
    label = Label(
        text=text,
        color=color,
        font_size=dp(size),
        bold=bold,
        markup=markup,
        halign="left",
        valign="middle",
        size_hint_y=None,
        height=dp(height),
    )
    label.bind(size=lambda instance, value: setattr(instance, "text_size", (value[0], None)))
    return label


def input_field(hint: str, *, password=False, multiline=False, text="") -> TextInput:
    field = TextInput(
        text=text,
        hint_text=hint,
        password=password,
        multiline=multiline,
        size_hint_y=None if not multiline else (1 if multiline else None),
        height=dp(50) if not multiline else dp(110),
        background_normal="",
        background_active="",
        background_color=(0.035, 0.022, 0.06, 1),
        foreground_color=TEXT,
        hint_text_color=MUTED,
        cursor_color=TEXT,
        padding=(dp(12), dp(13)),
        font_size=dp(14),
    )
    with field.canvas.after:
        edge_color = Color(*PURPLE[:3], .55)
        edge = Line(rectangle=(field.x, field.y, field.width, field.height), width=1)
    def update_edge(*_):
        edge.rectangle = (field.x, field.y, field.width, field.height)
        edge_color.rgba = GOLD if field.focus else (*PURPLE[:3], .55)
    field.bind(pos=update_edge, size=update_edge, focus=update_edge)
    return field


def adaptive_popup(title: str, content, height: float, **kwargs) -> Popup:
    width = 0.96 if Window.width < dp(600) else 0.72
    return Popup(
        title=title,
        content=content,
        size_hint=(width, min(0.92, height)),
        **kwargs,
    )


class CinematicIntro(FloatLayout):
    """Entrada HUD original inspirada en la fluidez de Caja Fantasma."""

    def __init__(self, *, language: str, on_open: Callable, on_complete: Callable, **kwargs):
        super().__init__(**kwargs)
        self.language = normalize_language(language)
        self.on_open = on_open
        self.on_complete = on_complete
        self._done = False
        with self.canvas.before:
            self._bg_color = Color(*BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            self._frame_color = Color(*GOLD[:3], 0.38)
            self._frame = Line(rectangle=(self.x, self.y, self.width, self.height), width=1)
            self._grid_color = Color(0.50, 0.22, 0.68, 0.09)
            self._grid_lines = [Line(points=(), width=0.7) for _ in range(8)]
        self.bind(pos=self._layout_intro, size=self._layout_intro)

        self.scan = Widget(size_hint=(None, None), height=dp(2), opacity=0)
        with self.scan.canvas:
            Color(0.74, 0.39, 1.0, 0.65)
            self._scan_rect = Rectangle(pos=self.scan.pos, size=self.scan.size)
        self.scan.bind(
            pos=lambda instance, _value: setattr(self._scan_rect, "pos", instance.pos),
            size=lambda instance, _value: setattr(self._scan_rect, "size", instance.size),
        )
        self.add_widget(self.scan)

        self.stage = ChestStage(
            opened=False,
            caption=translate("intro_title", self.language),
            size_hint=(None, None),
        )
        self.stage.opacity = 0
        self.add_widget(self.stage)

        self.progress_track = Widget(size_hint=(None, None), height=dp(3))
        with self.progress_track.canvas:
            Color(0.10, 0.25, 0.28, 0.85)
            self._progress_bg = RoundedRectangle(
                pos=self.progress_track.pos, size=self.progress_track.size, radius=[dp(2)]
            )
        self.progress_track.bind(pos=self._sync_progress_bg, size=self._sync_progress_bg)
        self.add_widget(self.progress_track)
        self.progress = Widget(size_hint=(None, None), height=dp(3), width=0)
        with self.progress.canvas:
            Color(*GOLD)
            self._progress_fill = RoundedRectangle(
                pos=self.progress.pos, size=self.progress.size, radius=[dp(2)]
            )
        self.progress.bind(
            pos=lambda instance, _value: setattr(self._progress_fill, "pos", instance.pos),
            size=lambda instance, _value: setattr(self._progress_fill, "size", instance.size),
        )
        self.add_widget(self.progress)

        self.hint = make_label(translate("skip_intro", self.language), 10, MUTED, True, 28)
        self.hint.halign = "center"
        self.hint.opacity = 0
        self.hint.size_hint = (None, None)
        self.add_widget(self.hint)
        Clock.schedule_once(self._start, 0.08)

    def _sync_progress_bg(self, *_):
        self._progress_bg.pos = self.progress_track.pos
        self._progress_bg.size = self.progress_track.size

    def _layout_intro(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        inset = dp(22 if self.width < dp(620) else 46)
        self._frame.rectangle = (
            self.x + inset,
            self.y + inset,
            max(0, self.width - inset * 2),
            max(0, self.height - inset * 2),
        )
        for index, line in enumerate(self._grid_lines):
            fraction = (index + 1) / 9
            if index % 2:
                x = self.x + self.width * fraction
                line.points = (x, self.y, x, self.top)
            else:
                y = self.y + self.height * fraction
                line.points = (self.x, y, self.right, y)
        self.scan.width = self.width * 1.1
        self.scan.x = self.x - self.width * 0.05
        stage_width = min(dp(690), max(dp(285), self.width * 0.82))
        self.stage.width = stage_width
        self.stage._adapt()
        self.stage.x = self.center_x - stage_width / 2
        self.stage.y = self.center_y - self.stage.height / 2 + dp(28)
        bar_width = min(dp(300), self.width * 0.58)
        self.progress_track.size = (bar_width, dp(3))
        self.progress_track.pos = (self.center_x - bar_width / 2, max(dp(42), self.stage.y - dp(34)))
        self.progress.height = dp(3)
        self.progress.pos = self.progress_track.pos
        self.hint.size = (min(dp(360), self.width - dp(32)), dp(28))
        self.hint.pos = (self.center_x - self.hint.width / 2, dp(12))

    def _start(self, *_):
        self._layout_intro()
        self.scan.y = self.top
        self.scan.opacity = 0.88
        Animation(y=self.y, duration=2.4, t="in_out_quad").start(self.scan)
        Animation(opacity=1, duration=0.38, t="out_cubic").start(self.stage)
        target_width = self.progress_track.width
        Animation(width=target_width, duration=3.0, t="out_quart").start(self.progress)
        Clock.schedule_once(self._open_chest, 0.72)
        Clock.schedule_once(lambda *_: Animation(opacity=1, duration=0.3).start(self.hint), 1.8)
        Clock.schedule_once(self.finish, 3.45)

    def _open_chest(self, *_):
        if self._done:
            return
        self.on_open()
        self.stage.chest.set_opened(True, animate=True)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.finish()
            return True
        return super().on_touch_down(touch)

    def finish(self, *_):
        if self._done:
            return
        self._done = True
        for widget in (self.scan, self.stage, self.progress, self.hint):
            Animation.cancel_all(widget)
        fade = Animation(opacity=0, duration=0.28, t="out_cubic")
        fade.bind(on_complete=lambda *_: self._complete())
        fade.start(self)

    def _complete(self):
        if self.parent is not None:
            self.parent.remove_widget(self)
        self.on_complete()


class LankdeaApp(App):
    title = "Lankdea"

    def build(self):
        if Metrics.density <= 0:
            # Algunos controladores SDL de Windows devuelven DPI=0. Evita que
            # todos los tamaños dp se conviertan en cero y dejen la vista vacía.
            Metrics.density = 1
            Metrics.dpi = 96
        Window.clearcolor = BG
        if platform != "android":
            try:
                # Estas propiedades ya están expresadas en coordenadas del
                # sistema; aplicar dp aquí duplica la escala DPI en Windows.
                Window.minimum_width = 360
                Window.minimum_height = 360
            except Exception:
                pass
        self.edition = EditionConfig.load()
        self.language = "es"
        self.device = self._device_name()
        data_dir = Path(os.environ.get("LANKDEA_DATA_DIR", self.user_data_dir))
        self.repository = LocalVaultRepository(data_dir / "lankdea_vault_v2.json", self.device)
        self.legacy_path = data_dir / "lankdea_cofre.json"
        self._pending_security_message = ""
        self._pending_file_action = None
        self._file_busy = False
        self._auth_busy = False
        self._last_activity = time.monotonic()
        self._enable_platform_security()
        self._remove_legacy_totp_qr()
        self.app_root = FloatLayout()
        with self.app_root.canvas.before:
            Color(*BG)
            background = Rectangle(pos=self.app_root.pos, size=self.app_root.size)
        self.app_root.bind(pos=lambda instance, value: setattr(background, "pos", value),
                           size=lambda instance, value: setattr(background, "size", value))
        self.root_box = BoxLayout(orientation="vertical")
        self.app_root.add_widget(self.root_box)
        self._clipboard_value = ""
        self.peer_server: PeerSyncServer | None = None
        self.adb_bridge: AdbReverseBridge | None = None
        self._peer_poll_event = None
        self._peer_sync_busy = False
        self._last_peer_sync = ""
        self._assistant_voice_event = None
        self._sounds = {
            "open": SoundLoader.load(str(asset("sounds/chest_open.wav"))),
            "close": SoundLoader.load(str(asset("sounds/chest_close.wav"))),
            "welcome": SoundLoader.load(str(asset("sounds/assistant_welcome.wav"))),
        }
        for sound in self._sounds.values():
            if sound:
                sound.volume = 0.72
        if self._sounds.get("welcome"):
            self._sounds["welcome"].volume = 0.92
        Window.bind(on_touch_down=self._record_activity, on_key_down=self._record_activity)
        self._idle_event = Clock.schedule_interval(self._check_idle_lock, 15)
        self.show_unlock()
        self.startup_intro = CinematicIntro(
            language=self.language,
            on_open=lambda: self._play_sound("open"),
            on_complete=lambda: None,
        )
        self.app_root.add_widget(self.startup_intro)
        return self.app_root

    def _enable_platform_security(self):
        if platform != "android":
            return
        try:
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            layout_params = autoclass("android.view.WindowManager$LayoutParams")
            activity.getWindow().addFlags(layout_params.FLAG_SECURE)
        except Exception:
            self._pending_security_message = (
                "Android no pudo bloquear capturas de pantalla. Evita mostrar secretos "
                "hasta reiniciar la app."
            )

    def _remove_legacy_totp_qr(self):
        old_qr = Path(self.user_data_dir) / "lankdea_authenticator.png"
        try:
            old_qr.unlink(missing_ok=True)
        except OSError:
            self._pending_security_message = (
                "No se pudo retirar un QR antiguo de Authenticator. Elimínalo desde "
                f"la carpeta privada de Lankdea: {old_qr}"
            )

    def _record_activity(self, *_):
        self._last_activity = time.monotonic()
        return False

    def _check_idle_lock(self, *_):
        if not self.repository.unlocked:
            return
        settings = self.repository.snapshot().get("settings", {})
        try:
            timeout = int(settings.get("auto_lock_seconds", 300))
        except (TypeError, ValueError):
            timeout = 300
        timeout = min(3600, max(60, timeout))
        if time.monotonic() - self._last_activity >= timeout:
            self.lock(immediate=True)

    def _device_name(self) -> str:
        if platform == "android":
            return "android"
        try:
            return f"desktop-{socket.gethostname()[:30]}"
        except Exception:
            return "desktop"

    def clear(self):
        if self._assistant_voice_event is not None:
            self._assistant_voice_event.cancel()
            self._assistant_voice_event = None
        self.root_box.clear_widgets()

    def t(self, key: str, default: str | None = None) -> str:
        return translate(key, self.language, default=default)

    @staticmethod
    def _language_option(code: str) -> str:
        language = next(item for item in LANGUAGES if item.code == code)
        return f"{language.short}  •  {language.name}"

    def _language_spinner(self) -> Spinner:
        spinner = Spinner(
            text=self._language_option(self.language),
            values=[self._language_option(item.code) for item in LANGUAGES],
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=PURPLE_DARK,
            color=TEXT,
            font_size=dp(14),
            font_name="Roboto",
        )

        def select(_spinner, value):
            for language in LANGUAGES:
                if value == self._language_option(language.code):
                    if language.code == self.language:
                        return
                    self.language = language.code
                    if self.repository.unlocked:
                        self.repository.update_settings(ui_language=self.language)
                        self.show_main()
                    else:
                        self.show_unlock()
                    return

        spinner.bind(text=select)
        return spinner

    def _play_sound(self, name: str):
        enabled = True
        if self.repository.unlocked:
            enabled = bool(
                self.repository.snapshot().get("settings", {}).get("sounds_enabled", True)
            )
        sound = self._sounds.get(name)
        if enabled and sound:
            sound.stop()
            sound.play()

    def _animations_enabled(self) -> bool:
        if not self.repository.unlocked:
            return True
        return bool(
            self.repository.snapshot().get("settings", {}).get("animations_enabled", True)
        )

    def _play_assistant_welcome(self, *_):
        self._assistant_voice_event = None
        if not self.repository.unlocked:
            return
        settings = self.repository.snapshot().get("settings", {})
        if not settings.get("assistant_enabled", True) or self.language != "es":
            return
        self._play_sound("welcome")

    def popup(self, title: str, message: str):
        box = Card(orientation="vertical", padding=dp(16), spacing=dp(12))
        box.add_widget(make_label(message, 13, TEXT, False, 125))
        close = VaultButton(text=self.t("close"), accent=True)
        box.add_widget(close)
        popup = adaptive_popup(title, box, 0.45)
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def show_unlock(self, message: str = ""):
        self.clear()
        page = ScrollView(do_scroll_x=False, bar_width=dp(4), scroll_y=1)
        outer = ResponsiveColumn(
            orientation="vertical",
            spacing=dp(14),
            size_hint=(None, None),
        )
        page.bind(width=lambda instance, value: setattr(outer, "width", value))
        outer.width = page.width
        outer.bind(minimum_height=outer.setter("height"))
        stage = ChestStage(opened=False, caption=self.t("encrypted_vault"))
        self.unlock_chest = stage.chest
        outer.add_widget(stage)

        form = Card(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(10),
            size_hint_y=None,
        )
        form.bind(minimum_height=form.setter("height"))
        form.add_widget(make_label(self.t("secure_access"), 24, TEXT, True, 38))
        language_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(44))
        language_row.add_widget(make_label(self.t("language"), 11, GOLD, True, 44))
        language_row.add_widget(self._language_spinner())
        form.add_widget(language_row)
        if self.repository.exists:
            form.add_widget(
                make_label(
                    self.t("unlock_help"),
                    12,
                    MUTED,
                    False,
                    48,
                )
            )
            password = input_field(self.t("master_password"), password=True)
            form.add_widget(password)
            open_button = VaultButton(text=self.t("verify_open"), accent=True)

            def begin_unlock(*_):
                if not password.text:
                    self.show_unlock("Escribe tu contraseña maestra.")
                    return
                open_button.disabled = True
                password.disabled = True
                open_button.text = self.t("checking")
                self.unlock(password.text)

            open_button.bind(on_release=begin_unlock)
            password.bind(on_text_validate=begin_unlock)
            form.add_widget(open_button)
        else:
            form.add_widget(
                make_label(
                    self.t("create_help"),
                    12,
                    MUTED,
                    False,
                    52,
                )
            )
            password = input_field(self.t("new_master_password"), password=True)
            confirm = input_field(self.t("repeat_password"), password=True)
            form.add_widget(password)
            form.add_widget(confirm)
            create = VaultButton(text=self.t("create_vault"), accent=True)
            create.bind(on_release=lambda *_: self.create_vault(password.text, confirm.text, False))
            password.bind(on_text_validate=lambda *_: setattr(confirm, "focus", True))
            confirm.bind(
                on_text_validate=lambda *_: self.create_vault(
                    password.text, confirm.text, False
                )
            )
            form.add_widget(create)
            if self.legacy_path.exists():
                migrate = VaultButton(text="Migrar cofre anterior", compact=True)
                migrate.bind(on_release=lambda *_: self.create_vault(password.text, confirm.text, True))
                form.add_widget(migrate)
        if message:
            form.add_widget(make_label(message, 11, DANGER, True, 28))
        outer.add_widget(form)
        outer.add_widget(
            make_label(
                f"Versión {__version__}  •  Autor: OscarD0823  •  Sin anuncios  •  Sin rastreo",
                10,
                MUTED,
                False,
                34,
            )
        )
        updates = VaultButton(text=self.t("updates_help"), compact=True)
        updates.bind(on_release=lambda *_: self.updates_menu())
        outer.add_widget(updates)
        page.add_widget(outer)
        backdrop = VaultBackdrop()
        backdrop.add_widget(page)
        self.root_box.add_widget(backdrop)
        Clock.schedule_once(lambda *_: setattr(password, "focus", True), 0.15)

    def create_vault(self, password: str, confirmation: str, migrate: bool):
        validation_error = master_password_error(password)
        if validation_error:
            self.show_unlock(validation_error)
            return
        if password != confirmation:
            self.show_unlock("Las contraseñas no coinciden.")
            return
        try:
            if migrate:
                count = migrate_legacy_file(self.legacy_path, self.repository, password)
                self.repository.update_settings(ui_language=self.language)
                self.popup("Migración terminada", f"Se migraron {count} registros. El archivo anterior quedó respaldado.")
            else:
                self.repository.create(password)
                self.repository.update_settings(ui_language=self.language)
            self._enter_vault()
        except Exception as exc:
            self.show_unlock(str(exc))

    def unlock(self, password: str):
        if self._auth_busy:
            return
        self._auth_busy = True
        def worker():
            try:
                document = self.repository.unlock(password)
            except Exception:
                Clock.schedule_once(lambda _dt: finished(None), 0)
            else:
                Clock.schedule_once(lambda _dt: finished(document), 0)
        def finished(document):
            self._auth_busy = False
            if document is None or not self.repository.unlocked:
                self.show_unlock("No se pudo abrir el cofre." if self.language == "es" else "Could not open the vault.")
                return
            self._unlocked_document(document)
        threading.Thread(target=worker, daemon=True).start()

    def _unlocked_document(self, document):
        settings = document.get("settings", {})
        self.language = normalize_language(settings.get("ui_language", self.language))
        if settings.get("totp_enabled") and settings.get("totp_secret"):
            self._ask_totp(str(settings["totp_secret"]))
        else:
            self._enter_vault()

    def _enter_vault(self):
        self._record_activity()
        try:
            retired = retire_legacy_artifacts(self.legacy_path, self.repository)
            if retired:
                self._pending_security_message = (
                    "Se retiraron copias antiguas que contenían su propia llave. "
                    "Quedó un respaldo protegido con tu contraseña actual."
                )
        except (OSError, VaultCryptoError) as exc:
            self._pending_security_message = (
                "El cofre abrió, pero no se pudo proteger una copia heredada: "
                f"{exc}"
            )
        self._play_sound("open")
        chest = getattr(self, "unlock_chest", None)
        if chest:
            chest.set_opened(
                True,
                animate=self._animations_enabled(),
                on_complete=self.show_main,
            )
        else:
            self.show_main()

    def _ask_totp(self, secret: str):
        box = Card(orientation="vertical", padding=dp(16), spacing=dp(12))
        box.add_widget(make_label("Paso 2 de 2", 17, TEXT, True, 32))
        box.add_widget(
            make_label(
                "Escribe el código de seis dígitos que muestra tu app Authenticator.",
                12,
                MUTED,
                False,
                42,
            )
        )
        code = input_field("Código de 6 dígitos")
        code.input_filter = "int"
        box.add_widget(code)
        status = make_label("", 11, DANGER, True, 28)
        box.add_widget(status)
        actions = AdaptiveGrid(item_count=2, row_height=42, spacing=dp(8))
        cancel = VaultButton(text="Cancelar", compact=True)
        button = VaultButton(text="Entrar", accent=True, compact=True)
        actions.add_widget(cancel)
        actions.add_widget(button)
        box.add_widget(actions)
        popup = adaptive_popup("Authenticator", box, 0.60, auto_dismiss=False)
        state = {"attempts": 0, "busy": False, "last_code": ""}

        def verify(*_):
            clean_code = code.text.strip()
            if state["busy"] or clean_code == state["last_code"]:
                return
            if len(clean_code) != 6:
                status.text = "El código debe tener exactamente 6 dígitos."
                return
            state["busy"] = True
            state["last_code"] = clean_code
            button.disabled = True
            if verify_totp_code(secret, clean_code):
                popup.dismiss()
                self._enter_vault()
                return

            state["attempts"] += 1
            state["busy"] = False
            button.disabled = False
            if state["attempts"] >= 5:
                popup.dismiss()
                self.repository.lock()
                self.show_unlock(
                    "Se agotaron los intentos del código. Vuelve a ingresar."
                )
                return
            remaining = 5 - state["attempts"]
            status.text = (
                f"Código incorrecto o vencido. Quedan {remaining} intentos."
            )
            code.text = ""
            Clock.schedule_once(lambda *_: setattr(code, "focus", True), 0.05)

        def cancel_login(*_):
            popup.dismiss()
            self.repository.lock()
            self.show_unlock()

        def auto_verify(_field, value):
            clean_code = value.strip()
            if len(clean_code) == 6 and clean_code.isdigit():
                Clock.schedule_once(verify, 0.08)

        button.bind(on_release=verify)
        code.bind(on_text_validate=verify)
        code.bind(text=auto_verify)
        cancel.bind(on_release=cancel_login)
        popup.open()
        Clock.schedule_once(lambda *_: setattr(code, "focus", True), 0.1)

    def show_main(self):
        self.clear()
        shell = ScrollView(do_scroll_x=False, bar_width=dp(4))
        body = BoxLayout(
            orientation="vertical",
            padding=(dp(16), dp(12)),
            spacing=dp(10),
            size_hint=(1, None),
        )
        body.bind(minimum_height=body.setter("height"))
        # Dale el tamaño real antes de añadir hijos fijos; Kivy puede reducirlos
        # a cero si calcula el primer layout sobre el tamaño inicial de 100 px.
        backdrop = VaultBackdrop()
        backdrop.add_widget(shell)
        self.root_box.add_widget(backdrop)
        shell.add_widget(body)
        body.width = shell.width
        def adapt_body(*_):
            side = max(dp(12), (shell.width - dp(1180)) / 2)
            body.padding = (side, dp(12))
        shell.bind(size=adapt_body)
        adapt_body()
        self.hero = HeroBanner(self.edition)
        self.hero.subtitle_label.text = self.t("personal_vault")
        body.add_widget(self.hero)
        body.bind(
            size=lambda instance, value: self.hero.adapt_to_view(shell.width, shell.height)
        )
        welcome = AssistantWelcome(language=self.language)
        body.add_widget(welcome)
        welcome._present_event = Clock.schedule_once(welcome.present, 0.08)
        action_count = 7
        actions = AdaptiveGrid(item_count=action_count, row_height=42, min_cell_width=112, spacing=dp(8))
        definitions = [
            (self.t("new_credential"), self.add_password, True),
            (self.t("new_note"), self.add_note, False),
            (self.t("add_file"), self.add_file, False),
            (self.t("backup"), self.export_backup, False),
            (self.t("pc_mobile"), self.direct_sync, False),
            (self.t("settings"), self.settings, False),
            (self.t("lock"), self.lock, False),
        ]
        for text, callback, accent in definitions:
            button = VaultButton(text=text, accent=accent, compact=True)
            button.bind(on_release=lambda _, fn=callback: fn())
            actions.add_widget(button)
        body.add_widget(actions)

        self.search = input_field(self.t("search_short"))
        self.search.bind(text=lambda _, value: self.refresh_items(value))
        body.add_widget(self.search)
        self.status_label = make_label(self._status_text(), 11, MUTED, False, 24)
        body.add_widget(self.status_label)
        item_scroll = ScrollView(do_scroll_x=False, bar_width=dp(5), size_hint_y=None, height=dp(220))
        def adapt_list(*_):
            # Conserva al menos 180dp para contenido. Si la ventana es muy baja,
            # el panel completo puede desplazarse además de la lista interna.
            fixed = sum(child.height for child in body.children if child is not item_scroll) + dp(85)
            item_scroll.height = max(dp(180), shell.height - fixed)
        shell.bind(size=adapt_list)
        welcome.bind(height=adapt_list)
        actions.bind(height=adapt_list)
        self.hero.bind(height=adapt_list)
        self.item_list = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=(0, 0, dp(5), dp(8)))
        self.item_list.bind(minimum_height=self.item_list.setter("height"))
        item_scroll.add_widget(self.item_list)
        body.add_widget(item_scroll)
        Clock.schedule_once(adapt_list, 0)
        self.item_scroll = item_scroll
        self.refresh_items("")
        self._start_peer_services()
        if self._pending_file_action:
            action = self._pending_file_action
            self._pending_file_action = None
            Clock.schedule_once(lambda _dt: action(), 0.25)
        if self._pending_security_message:
            message = self._pending_security_message
            self._pending_security_message = ""
            Clock.schedule_once(
                lambda _dt: self.popup("Aviso de seguridad", message), 0.2
            )
        else:
            # Espera a que termine el sonido de apertura para que la voz se entienda.
            self._assistant_voice_event = Clock.schedule_once(
                self._play_assistant_welcome, 0.78
            )

    def _status_text(self) -> str:
        document = self.repository.snapshot()
        count = len(active_items(document))
        if platform == "android":
            peer = "Enlace automático" if self._peer_enabled() else "PC sin enlazar"
        else:
            peer = "PC disponible" if self.peer_server else "Enlace PC apagado"
        suffix = f"  •  {peer}"
        if self._last_peer_sync:
            suffix += f"  •  {self._last_peer_sync}"
        return self.t("status_summary").format(count=count, revision=document.get('revision', 0)) + suffix

    def refresh_items(self, query: str = ""):
        if not self.repository.unlocked or not hasattr(self, "item_list"):
            return
        document = self.repository.snapshot()
        items = search_items(document, query)
        items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        self.item_list.clear_widgets()
        if not items:
            empty = Card(orientation="vertical", padding=dp(16), size_hint_y=None, height=dp(100))
            empty.add_widget(make_label(self.t("empty_vault") if not query else self.t("no_matches"), 16, TEXT, True, 32))
            empty.add_widget(make_label(self.t("empty_hint"), 12, MUTED, False, 26))
            self.item_list.add_widget(empty)
        for item in items:
            self.item_list.add_widget(self._item_card(item))
        self.status_label.text = self._status_text()

    def _item_card(self, item: dict[str, Any]) -> Card:
        is_password = item.get("type") == "password"
        height = dp(188 if is_password else 155)
        card = Card(orientation="vertical", padding=dp(13), spacing=dp(5), size_hint_y=None, height=height, color=PANEL_LIGHT)
        card.add_widget(make_label(str(item.get("title", "Sin título")), 16, TEXT, True, 28))
        if is_password:
            card.add_widget(make_label(f"{self.t('service')}: {item.get('service') or '—'}", 12, MUTED, False, 22))
            card.add_widget(make_label(f"{self.t('username')}: {item.get('username') or '—'}", 12, MUTED, False, 22))
            card.add_widget(make_label(self.t("password") + ": ••••••••••••", 12, GOLD, True, 22))
            primary_value = str(item.get("password", ""))
            primary_label = self.t("copy_password")
        elif item.get("type") == "file":
            metadata = item["attachment"]
            card.add_widget(make_label(f"{metadata['mime_type']}  •  {metadata['size'] / 1048576:.2f} MiB", 12, GOLD, False, 28))
            card.add_widget(make_label(self.t("encrypted_by_you"), 12, MUTED, False, 30))
            primary_value = ""
            primary_label = self.t("export_file")
        else:
            content = str(item.get("content", ""))
            preview = content if len(content) <= 170 else content[:167] + "…"
            card.add_widget(make_label(preview or "Nota vacía", 12, MUTED, False, 58))
            primary_value = content
            primary_label = self.t("copy_note")
        row = GridLayout(cols=3, spacing=dp(7), size_hint_y=None, height=dp(40))
        copy_button = VaultButton(text=primary_label, accent=True, compact=True)
        edit_button = VaultButton(text=self.t("edit"), compact=True)
        delete_button = VaultButton(text=self.t("delete"), danger=True, compact=True)
        copy_button.bind(on_release=lambda *_: self.export_file(item) if item.get("type") == "file" else self.copy_secure(primary_value))
        edit_button.bind(on_release=lambda *_: self.edit_item(item))
        delete_button.bind(on_release=lambda *_: self.confirm_delete(item))
        row.add_widget(copy_button)
        row.add_widget(edit_button)
        row.add_widget(delete_button)
        card.add_widget(row)
        return card

    def add_password(self):
        self._edit_password_popup(None)

    def add_note(self):
        self._edit_note_popup(None)

    def _pick_file(self, callback: Callable, *, save=False, name="archivo.bin"):
        if self._file_busy:
            return
        if platform == "android":
            def selected(value):
                if not value:
                    return
                action = lambda: callback(value)
                if self.repository.unlocked:
                    action()
                else:
                    self._pending_file_action = action
                    self.show_unlock(self.t("unlock_file_action"))
            try:
                android_pick(save=save, name=safe_filename(name), callback=selected)
            except Exception as exc:
                self.popup(self.t("error"), str(exc))
            return
        box = Card(orientation="vertical", padding=dp(12), spacing=dp(8))
        chooser = FileChooserListView(path=str(Path.home()), dirselect=False)
        box.add_widget(chooser)
        filename = input_field(self.t("filename"), text=safe_filename(name)) if save else None
        if filename is not None:
            box.add_widget(filename)
        row = GridLayout(cols=2, size_hint_y=None, height=dp(46), spacing=dp(8))
        choose = VaultButton(text=self.t("save") if save else self.t("select"), accent=True)
        cancel = VaultButton(text=self.t("cancel"))
        row.add_widget(cancel)
        row.add_widget(choose)
        box.add_widget(row)
        popup = adaptive_popup(self.t("export_file") if save else self.t("add_file"), box, 0.86)
        def selected(*_):
            value = str(Path(chooser.path) / safe_filename(filename.text)) if save else (chooser.selection[0] if chooser.selection else "")
            if not value:
                return
            popup.dismiss()
            callback(value)
        choose.bind(on_release=selected)
        cancel.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def add_file(self):
        def selected(value):
            def import_file():
                name, size = selected_details(value)
                with open_selected(value, "rb") as stream:
                    return self.repository.import_attachment(stream, name=name, size=size)
            self._file_task(self.t("encrypting"), import_file, lambda _result: self.refresh_items(self.search.text))
        self._pick_file(selected)

    def _file_task(self, label: str, fn: Callable, on_success: Callable):
        if self._file_busy:
            return
        self._file_busy = True
        def worker():
            try:
                result = fn()
            except Exception as exc:
                Clock.schedule_once(lambda _dt, error=exc: done(None, error), 0)
            else:
                Clock.schedule_once(lambda _dt: done(result, None), 0)
        def done(result, error):
            self._file_busy = False
            if error:
                self._async_error(error)
            elif self.repository.unlocked:
                on_success(result)
                if hasattr(self, "status_label"):
                    self.status_label.text = self._status_text()
        if hasattr(self, "status_label"):
            self.status_label.text = label
        threading.Thread(target=worker, daemon=True).start()

    def export_file(self, item: dict):
        metadata = item["attachment"]
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
        box.add_widget(make_label(self.t("plaintext_warning"), 13, GOLD, False, 110))
        export = VaultButton(text=self.t("export_file"), accent=True)
        box.add_widget(export)
        popup = adaptive_popup(self.t("export_file"), box, 0.48)
        def selected(value):
            def export_selected():
                with open_selected(value, "xb") as stream:
                    self.repository.export_attachment(metadata["file_id"], stream)
                return value
            self._file_task(self.t("decrypting"), export_selected,
                            lambda path: self.popup(self.t("export_file"), self.t("exported") + "\n" + path))
        export.bind(on_release=lambda *_: (popup.dismiss(), self._pick_file(selected, save=True, name=metadata["filename"])))
        popup.open()

    def edit_item(self, item: dict[str, Any]):
        if item.get("type") == "file":
            box = Card(orientation="vertical", padding=dp(14), spacing=dp(10))
            title = input_field(self.t("title"), text=item["title"])
            box.add_widget(title)
            save = VaultButton(text=self.t("save"), accent=True)
            box.add_widget(save)
            popup = adaptive_popup(self.t("edit"), box, 0.4)
            def commit(*_):
                record = dict(item, title=title.text.strip() or item["attachment"]["filename"])
                self.repository.upsert_item(record)
                popup.dismiss()
                self.refresh_items(self.search.text)
            save.bind(on_release=commit)
            popup.open()
        elif item.get("type") == "password":
            self._edit_password_popup(item)
        else:
            self._edit_note_popup(item)

    def _edit_password_popup(self, item: dict[str, Any] | None):
        item = dict(item or {})
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
        service = input_field(self.t("service"), text=str(item.get("service", "")))
        username = input_field(self.t("username"), text=str(item.get("username", "")))
        password = input_field(
            self.t("password"), password=True, text=str(item.get("password", ""))
        )
        reveal = VaultButton(text=self.t("show_password"), compact=True)
        notes = input_field(self.t("optional_notes"), multiline=True, text=str(item.get("notes", "")))
        for field in (service, username, password, reveal, notes):
            box.add_widget(field)
        save = VaultButton(text=self.t("save_credential"), accent=True)
        box.add_widget(save)
        popup = adaptive_popup(self.t("edit_credential") if item else self.t("new_credential"), box, 0.82)

        def commit(*_):
            if not service.text.strip() or not password.text:
                self.popup("Faltan datos", "Escribe al menos el servicio y la contraseña.")
                return
            record = item or new_item("password", self.device)
            record.update(
                title=service.text.strip(),
                service=service.text.strip(),
                username=username.text.strip(),
                password=password.text,
                notes=notes.text.strip(),
            )
            self.repository.upsert_item(record)
            popup.dismiss()
            self.refresh_items(self.search.text)

        def toggle_reveal(*_):
            password.password = not password.password
            reveal.text = (
                self.t("show_password") if password.password else self.t("hide_password")
            )

        save.bind(on_release=commit)
        reveal.bind(on_release=toggle_reveal)
        popup.open()

    def _edit_note_popup(self, item: dict[str, Any] | None):
        item = dict(item or {})
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
        title = input_field(self.t("title"), text=str(item.get("title", "")))
        content = input_field(self.t("note_content"), multiline=True, text=str(item.get("content", "")))
        box.add_widget(title)
        box.add_widget(content)
        save = VaultButton(text=self.t("save_note"), accent=True)
        box.add_widget(save)
        popup = adaptive_popup(self.t("edit_note") if item else self.t("new_note"), box, 0.70)

        def commit(*_):
            if not title.text.strip() and not content.text.strip():
                self.popup("Nota vacía", "Escribe un título o contenido.")
                return
            record = item or new_item("note", self.device)
            record.update(title=title.text.strip() or "Nota", content=content.text.strip())
            self.repository.upsert_item(record)
            popup.dismiss()
            self.refresh_items(self.search.text)

        save.bind(on_release=commit)
        popup.open()

    def confirm_delete(self, item: dict[str, Any]):
        box = Card(orientation="vertical", padding=dp(16), spacing=dp(12))
        box.add_widget(make_label(f"¿Eliminar “{item.get('title', 'registro')}”?", 14, TEXT, True, 55))
        row = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = VaultButton(text="Cancelar")
        delete = VaultButton(text="Eliminar", danger=True)
        row.add_widget(cancel)
        row.add_widget(delete)
        box.add_widget(row)
        popup = adaptive_popup("Confirmar", box, 0.38)
        cancel.bind(on_release=lambda *_: popup.dismiss())

        def commit(*_):
            self.repository.delete_item(str(item["id"]))
            popup.dismiss()
            self.refresh_items(self.search.text)

        delete.bind(on_release=commit)
        popup.open()

    def copy_secure(self, value: str):
        if not self._copy_sensitive_clipboard(value):
            Clipboard.copy(value)
        self._clipboard_value = value
        Clock.unschedule(self._clear_clipboard)
        settings = self.repository.snapshot().get("settings", {}) if self.repository.unlocked else {}
        try:
            timeout = min(30, max(5, int(settings.get("clipboard_clear_seconds", 15))))
        except (TypeError, ValueError):
            timeout = 15
        Clock.schedule_once(self._clear_clipboard, timeout)
        self.popup(
            "Copiado",
            f"Se borrará del portapapeles en {timeout} segundos. "
            "Otros programas del dispositivo todavía podrían leerlo.",
        )

    def _copy_sensitive_clipboard(self, value: str) -> bool:
        if platform != "android":
            return False
        try:
            from jnius import autoclass

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            context = autoclass("android.content.Context")
            clip_data = autoclass("android.content.ClipData")
            bundle_class = autoclass("android.os.PersistableBundle")
            manager = activity.getSystemService(context.CLIPBOARD_SERVICE)
            clip = clip_data.newPlainText("", value)
            extras = bundle_class()
            extras.putBoolean("android.content.extra.IS_SENSITIVE", True)
            clip.getDescription().setExtras(extras)
            manager.setPrimaryClip(clip)
            return True
        except Exception:
            return False

    def _clear_clipboard(self, *_):
        try:
            if Clipboard.paste() == self._clipboard_value:
                if platform == "android":
                    try:
                        from jnius import autoclass

                        activity = autoclass("org.kivy.android.PythonActivity").mActivity
                        context = autoclass("android.content.Context")
                        manager = activity.getSystemService(context.CLIPBOARD_SERVICE)
                        manager.clearPrimaryClip()
                    except Exception:
                        Clipboard.copy("")
                else:
                    Clipboard.copy("")
        except Exception:
            pass
        self._clipboard_value = ""

    def settings(self):
        document = self.repository.snapshot()
        settings = document.get("settings", {})
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
        box.add_widget(make_label(self.t("security"), 18, TEXT, True, 32))
        box.add_widget(make_label(f"AES-256-GCM + scrypt  •  {self.t('encrypted_by_you')}", 11, GOLD, True, 24))
        language = VaultButton(text=f"{self.t('language')}: {language_name(self.language)}")
        change = VaultButton(text="Cambiar contraseña maestra")
        totp_text = "Desactivar Authenticator" if settings.get("totp_enabled") else "Activar Authenticator"
        totp = VaultButton(text=totp_text)
        sound = VaultButton(
            text="Sonidos: activados" if settings.get("sounds_enabled", True) else "Sonidos: apagados"
        )
        animations = VaultButton(
            text=(
                "Animaciones: activadas"
                if settings.get("animations_enabled", True)
                else "Animaciones: reducidas"
            )
        )
        assistant = VaultButton(
            text=(
                "Asistente al entrar: activado"
                if settings.get("assistant_enabled", True)
                else "Asistente al entrar: apagado"
            )
        )
        peer = VaultButton(text="Enlace PC + celular")
        backup = VaultButton(text="Crear respaldo cifrado")
        restore = VaultButton(text=self.t("restore_backup"))
        updates = VaultButton(text="Actualizaciones y ayuda")
        close = VaultButton(text=self.t("close"), accent=True)
        for button in (language, change, totp, sound, animations, assistant, peer, backup, restore, updates, close):
            box.add_widget(button)
        box.size_hint_y = None
        box.bind(minimum_height=box.setter("height"))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(box)
        popup = adaptive_popup(self.t("settings"), scroll, 0.88)
        language.bind(on_release=lambda *_: (popup.dismiss(), self.language_menu()))
        change.bind(on_release=lambda *_: (popup.dismiss(), self.change_passphrase()))
        if settings.get("totp_enabled"):
            totp.bind(on_release=lambda *_: (popup.dismiss(), self.disable_totp()))
        else:
            totp.bind(on_release=lambda *_: (popup.dismiss(), self.enable_totp()))
        sound.bind(on_release=lambda *_: self.toggle_sounds(sound))
        animations.bind(on_release=lambda *_: self.toggle_animations(animations))
        assistant.bind(on_release=lambda *_: self.toggle_assistant(assistant))
        peer.bind(on_release=lambda *_: (popup.dismiss(), self.peer_sync_menu()))
        backup.bind(on_release=lambda *_: self.export_backup())
        restore.bind(on_release=lambda *_: (popup.dismiss(), self.restore_backup()))
        updates.bind(on_release=lambda *_: (popup.dismiss(), self.updates_menu()))
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def language_menu(self):
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(9))
        box.add_widget(make_label(self.t("language"), 18, TEXT, True, 34))
        grid = AdaptiveGrid(
            item_count=len(LANGUAGES),
            row_height=42,
            min_cell_width=130,
            spacing=dp(7),
        )
        box.add_widget(grid)
        popup = adaptive_popup(self.t("language"), box, 0.82)
        for language in LANGUAGES:
            button = VaultButton(
                text=f"{language.short}  {language.name}",
                accent=language.code == self.language,
                compact=True,
            )

            def choose(*_, code=language.code):
                self.language = code
                self.repository.update_settings(ui_language=code)
                popup.dismiss()
                self.show_main()

            button.bind(on_release=choose)
            grid.add_widget(button)
        close = VaultButton(text=self.t("close"), compact=True)
        close.bind(on_release=lambda *_: popup.dismiss())
        box.add_widget(close)
        popup.open()

    def updates_menu(self):
        # Comprobación solo a petición: la aplicación funciona sin Internet.
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(10), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        box.add_widget(make_label(f"Lankdea Local {__version__}", 20, TEXT, True, 36))
        box.add_widget(make_label(
            "Actualiza con el ZIP completo: instalador Windows + APK + manual. "
            "Haz un respaldo y cierra el cofre antes de instalar. "
            "No desinstales Android: necesita la misma firma para conservar los datos.",
            13, TEXT, False, 130,
        ))
        status = make_label(
            "No se consultará Internet hasta que pulses Comprobar. "
            "Las descargas publicadas son públicas y no requieren cuenta GitHub.",
            12, MUTED, False, 100,
        )
        box.add_widget(status)
        check = VaultButton(text="Comprobar versión publicada")
        website = VaultButton(text="Abrir versiones en GitHub")
        close = VaultButton(text="Cerrar", accent=True)
        for button in (check, website, close):
            box.add_widget(button)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(box)
        dialog = adaptive_popup("Actualizaciones", scroll, 0.88)

        def completed(result):
            check.disabled = False
            status.text = result.message

        def check_now(*_):
            check.disabled = True
            status.text = "Consultando versiones; el cofre no se enviará a Internet."
            def worker():
                result = check_latest_release()
                Clock.schedule_once(lambda _dt: completed(result), 0)
            threading.Thread(target=worker, daemon=True).start()

        check.bind(on_release=check_now)
        website.bind(on_release=lambda *_: self.open_release_page())
        close.bind(on_release=lambda *_: dialog.dismiss())
        dialog.open()

    def open_release_page(self):
        try:
            if platform == "android":
                from jnius import autoclass
                intent_class = autoclass("android.content.Intent")
                uri_class = autoclass("android.net.Uri")
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                activity.startActivity(intent_class(intent_class.ACTION_VIEW, uri_class.parse(RELEASES_URL)))
            elif not webbrowser.open(RELEASES_URL):
                raise RuntimeError("No se encontró un navegador.")
        except Exception:
            self.popup("Versiones de Lankdea", f"Abre esta dirección en tu navegador:\n{RELEASES_URL}")

    def toggle_sounds(self, button: VaultButton | None = None):
        settings = self.repository.snapshot().get("settings", {})
        enabled = not bool(settings.get("sounds_enabled", True))
        self.repository.update_settings(sounds_enabled=enabled)
        if button:
            button.text = "Sonidos: activados" if enabled else "Sonidos: apagados"
        if enabled:
            self._play_sound("open")
        self.refresh_items(self.search.text)

    def toggle_animations(self, button: VaultButton | None = None):
        settings = self.repository.snapshot().get("settings", {})
        enabled = not bool(settings.get("animations_enabled", True))
        self.repository.update_settings(animations_enabled=enabled)
        if button:
            button.text = "Animaciones: activadas" if enabled else "Animaciones: reducidas"

    def toggle_assistant(self, button: VaultButton | None = None):
        settings = self.repository.snapshot().get("settings", {})
        enabled = not bool(settings.get("assistant_enabled", True))
        self.repository.update_settings(assistant_enabled=enabled)
        if button:
            button.text = (
                "Asistente al entrar: activado"
                if enabled
                else "Asistente al entrar: apagado"
            )
        if enabled:
            self._play_assistant_welcome()

    def change_passphrase(self):
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(9))
        current = input_field("Contraseña maestra actual", password=True)
        first = input_field("Nueva contraseña (12+ caracteres)", password=True)
        second = input_field("Repite la contraseña", password=True)
        save = VaultButton(text="Actualizar", accent=True)
        box.add_widget(current)
        box.add_widget(first)
        box.add_widget(second)
        box.add_widget(save)
        popup = adaptive_popup("Contraseña maestra", box, 0.52)

        def commit(*_):
            if not secrets.compare_digest(
                current.text.encode("utf-8"), self.repository.passphrase.encode("utf-8")
            ):
                self.popup("No se actualizó", "La contraseña maestra actual no coincide.")
                return
            validation_error = master_password_error(first.text)
            if validation_error or first.text != second.text:
                self.popup(
                    "No se actualizó",
                    validation_error or "Confirma exactamente la misma contraseña.",
                )
                return
            popup.dismiss()
            self.repository.change_passphrase(first.text)
            self.popup("Actualizada", "El cofre fue cifrado de nuevo con la nueva contraseña.")

        save.bind(on_release=commit)
        popup.open()

    def enable_totp(self):
        if qrcode is None:
            self.popup("No disponible", "Falta el módulo qrcode en esta compilación.")
            return
        secret = pyotp.random_base32()
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=f"Cofre {self.device}", issuer_name="Lankdea"
        )
        qr_buffer = BytesIO()
        qrcode.make(uri).save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        qr_texture = CoreImage(qr_buffer, ext="png").texture
        box = Card(orientation="vertical", padding=dp(12), spacing=dp(7))
        box.add_widget(
            make_label(
                "Escanea el QR. La app mostrará un código; escríbelo abajo para activar.",
                12,
                TEXT,
                True,
                48,
            )
        )
        box.add_widget(Image(texture=qr_texture))
        box.add_widget(make_label(f"Clave manual: {secret}", 10, GOLD, True, 36))
        code = input_field("Código actual de 6 dígitos")
        code.input_filter = "int"
        box.add_widget(code)
        status = make_label("", 11, DANGER, True, 28)
        box.add_widget(status)
        actions = AdaptiveGrid(item_count=2, row_height=42, spacing=dp(8))
        cancel = VaultButton(text="Cancelar", compact=True)
        enable = VaultButton(text="Confirmar y activar", accent=True, compact=True)
        actions.add_widget(cancel)
        actions.add_widget(enable)
        box.add_widget(actions)
        popup = adaptive_popup("Configurar Authenticator", box, 0.92, auto_dismiss=False)

        def commit(*_):
            clean_code = code.text.strip()
            if not verify_totp_code(secret, clean_code):
                status.text = "El código no coincide. Espera uno nuevo e inténtalo otra vez."
                code.text = ""
                Clock.schedule_once(lambda *_: setattr(code, "focus", True), 0.05)
                return
            self.repository.update_settings(totp_enabled=True, totp_secret=secret)
            popup.dismiss()
            self.refresh_items(self.search.text)
            self.popup(
                "Authenticator activado",
                "Desde ahora entrarás con la contraseña maestra y después con el código.",
            )

        enable.bind(on_release=commit)
        code.bind(on_text_validate=commit)
        cancel.bind(on_release=lambda *_: popup.dismiss())
        popup.open()
        Clock.schedule_once(lambda *_: setattr(code, "focus", True), 0.35)

    def disable_totp(self):
        self.repository.update_settings(totp_enabled=False, totp_secret="")
        self.popup("Authenticator", "El segundo paso quedó desactivado.")
        self.refresh_items(self.search.text)

    def export_backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if platform == "android":
            def selected(value):
                def write_bundle():
                    with open_selected(value, "xb") as stream:
                        self.repository.export_bundle_stream(stream)
                    return value
                self._file_task(self.t("backup"), write_bundle,
                                lambda path: self.popup(self.t("backup"), self.t("exported") + "\n" + path))
            self._pick_file(selected, save=True, name=f"lankdea_backup_{stamp}.lankdea")
            return
        target = self.repository.path.parent / "backups" / f"lankdea_backup_{stamp}.lankdea"
        self._file_task(self.t("backup"), lambda: self.repository.export_bundle(target),
                        lambda path: self.popup(self.t("backup"), self.t("exported") + f"\n{path}"))

    def restore_backup(self):
        def selected(value):
            box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
            box.add_widget(make_label(self.t("backup_password_help"), 12, MUTED, False, 60))
            password = input_field(self.t("backup_password"), password=True)
            restore = VaultButton(text=self.t("restore_backup"), accent=True)
            box.add_widget(password)
            box.add_widget(restore)
            popup = adaptive_popup(self.t("restore_backup"), box, 0.5)
            def begin(*_):
                phrase = password.text or None
                password.text = ""
                popup.dismiss()
                def restore_selected():
                    with open_selected(value, "rb") as stream:
                        return self.repository.restore_bundle(stream, phrase)
                self._file_task(self.t("restore_backup"), restore_selected,
                                lambda _result: self.refresh_items(self.search.text))
            restore.bind(on_release=begin)
            popup.open()
        self._pick_file(selected)

    def _peer_enabled(self) -> bool:
        if not self.repository.unlocked:
            return False
        settings = self.repository.snapshot().get("settings", {})
        return bool(settings.get("peer_enabled") and settings.get("peer_code"))

    def _start_peer_services(self):
        if not self._peer_enabled():
            return
        settings = self.repository.snapshot().get("settings", {})
        code = str(settings.get("peer_code", ""))
        if platform == "android":
            if self._peer_poll_event is None:
                self._peer_poll_event = Clock.schedule_interval(
                    lambda _dt: self._begin_peer_sync(manual=False), 8
                )
            Clock.schedule_once(lambda _dt: self._begin_peer_sync(manual=False), 1.2)
            return
        if self.peer_server is not None:
            return
        try:
            self.peer_server = PeerSyncServer(
                self.repository,
                code,
                self.device,
                on_update=lambda stats: Clock.schedule_once(
                    lambda _dt: self._peer_server_updated(stats), 0
                ),
            )
            self.peer_server.start()
            self.adb_bridge = AdbReverseBridge(self.peer_server.port)
            self.adb_bridge.start()
        except (OSError, PeerSyncError) as exc:
            self.peer_server = None
            self._last_peer_sync = f"Enlace no disponible: {exc}"

    def _stop_peer_services(self):
        if self._peer_poll_event is not None:
            self._peer_poll_event.cancel()
            self._peer_poll_event = None
        if self.peer_server is not None:
            self.peer_server.stop()
            self.peer_server = None
        if self.adb_bridge is not None:
            self.adb_bridge.stop()
            self.adb_bridge = None
        self._peer_sync_busy = False

    def _peer_server_updated(self, stats: dict[str, int]):
        if not self.repository.unlocked:
            return
        self._last_peer_sync = datetime.now().strftime("Celular %H:%M")
        if hasattr(self, "search"):
            self.refresh_items(self.search.text)

    def direct_sync(self):
        if platform != "android" or not self._peer_enabled():
            self.peer_sync_menu()
            return
        self._begin_peer_sync(manual=True)

    def peer_sync_menu(self):
        settings = self.repository.snapshot().get("settings", {})
        box = Card(orientation="vertical", padding=dp(14), spacing=dp(8))
        box.add_widget(make_label("Sincronización directa cifrada", 18, TEXT, True, 34))
        box.add_widget(
            make_label(
                "Ambas apps deben estar abiertas y usar la misma contraseña maestra.",
                11,
                MUTED,
                False,
                38,
            )
        )
        if platform != "android":
            code = str(settings.get("peer_code", "")) or generate_pair_code()
            if not settings.get("peer_code"):
                self.repository.update_settings(
                    peer_code=normalize_pair_code(code), peer_enabled=True
                )
                self._start_peer_services()
            code_field = input_field("Código de enlace", text=code)
            code_field.readonly = True
            address = make_label(
                f"PC: {local_ip()}:{self.peer_server.port if self.peer_server else DEFAULT_PORT}",
                12,
                GOLD,
                True,
                30,
            )
            info = make_label(
                "Escribe este código en el celular. La detección por Wi-Fi es automática.",
                11,
                MUTED,
                False,
                40,
            )
            usb_info = make_label(
                "Cable USB automático"
                if self.adb_bridge and self.adb_bridge.available
                else "Cable USB: instala Android Platform-Tools (ADB)",
                10,
                GOOD if self.adb_bridge and self.adb_bridge.available else MUTED,
                False,
                30,
            )
            regenerate = VaultButton(text="Crear código nuevo")
            close = VaultButton(text="Listo", accent=True)
            for widget in (code_field, address, info, usb_info, regenerate, close):
                box.add_widget(widget)
            popup = adaptive_popup("Enlazar celular", box, 0.72)

            def renew(*_):
                new_code = generate_pair_code()
                self.repository.update_settings(
                    peer_code=normalize_pair_code(new_code), peer_enabled=True
                )
                self._stop_peer_services()
                self._start_peer_services()
                code_field.text = new_code

            regenerate.bind(on_release=renew)
            close.bind(on_release=lambda *_: popup.dismiss())
            popup.open()
            self.refresh_items(self.search.text)
            return

        code = input_field("Código mostrado en el PC", text=str(settings.get("peer_code", "")))
        host = input_field(
            "IP del PC (opcional si usan el mismo Wi-Fi)",
            text=str(settings.get("peer_host", "")),
        )
        box.add_widget(code)
        box.add_widget(host)
        row = AdaptiveGrid(item_count=2, row_height=42, spacing=dp(8))
        save = VaultButton(text="Guardar y probar", accent=True, compact=True)
        usb = VaultButton(text="Usar cable USB", compact=True)
        row.add_widget(save)
        row.add_widget(usb)
        box.add_widget(row)
        close = VaultButton(text="Cerrar")
        box.add_widget(close)
        popup = adaptive_popup("Enlazar con el PC", box, 0.76)

        def commit(use_usb=False):
            clean_code = normalize_pair_code(code.text)
            if not valid_pair_code(clean_code):
                self.popup(
                    "Código inválido",
                    "Escribe exactamente el código de 16 caracteres mostrado por el PC.",
                )
                return
            target = "127.0.0.1" if use_usb else host.text.strip()
            self.repository.update_settings(
                peer_code=clean_code,
                peer_host=target,
                peer_enabled=True,
            )
            popup.dismiss()
            self._start_peer_services()
            self._begin_peer_sync(manual=True)

        save.bind(on_release=lambda *_: commit(False))
        usb.bind(on_release=lambda *_: commit(True))
        close.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def _begin_peer_sync(self, *, manual: bool):
        if platform != "android" or self._peer_sync_busy or not self._peer_enabled():
            return
        self._peer_sync_busy = True
        if manual and hasattr(self, "status_label"):
            self.status_label.text = "Buscando el cofre del PC…"

        def worker():
            try:
                result = self._peer_sync_worker()
            except Exception as exc:
                Clock.schedule_once(lambda _dt: self._peer_sync_failed(exc, manual), 0)
                return
            Clock.schedule_once(lambda _dt: self._peer_sync_finished(result, manual), 0)

        threading.Thread(target=worker, name="lankdea-peer-client", daemon=True).start()

    def _peer_sync_worker(self) -> dict[str, Any]:
        settings = self.repository.snapshot().get("settings", {})
        client = PeerSyncClient(self.repository, str(settings.get("peer_code", "")))
        candidates: list[tuple[str, int]] = []
        configured_host, configured_port = split_host(str(settings.get("peer_host", "")))
        if configured_host:
            candidates.append((configured_host, configured_port))
        discovered = discover_peer(timeout=2.2)
        if discovered and discovered not in candidates:
            candidates.append(discovered)
        usb = ("127.0.0.1", DEFAULT_PORT)
        if usb not in candidates:
            candidates.append(usb)
        last_error: Exception | None = None
        for host, port in candidates:
            try:
                return client.sync(host, port)
            except PeerSyncError as exc:
                last_error = exc
        raise last_error or PeerSyncError("No se encontró el cofre del PC.")

    def _peer_sync_finished(self, result: dict[str, Any], manual: bool):
        self._peer_sync_busy = False
        self._last_peer_sync = datetime.now().strftime("PC %H:%M")
        self.refresh_items(self.search.text)
        if manual:
            self.popup(
                "PC y celular sincronizados",
                f"Cambios recibidos: {result.get('imported', 0)}. Bloques transferidos: {result.get('blocks_transferred', 0)}. "
                f"Bloques pendientes: {result.get('blocks_missing', 0)}. El enlace seguirá automático.",
            )

    def _peer_sync_failed(self, exc: Exception, manual: bool):
        self._peer_sync_busy = False
        if self.repository.unlocked and hasattr(self, "status_label"):
            self.status_label.text = self._status_text()
        if manual:
            self.popup("No se encontró el PC", str(exc))

    def _run_async(self, label: str, fn: Callable, on_success: Callable):
        if hasattr(self, "status_label"):
            self.status_label.text = label

        def worker():
            try:
                result = fn()
            except Exception as exc:
                Clock.schedule_once(lambda _dt, error=exc: self._async_error(error), 0)
                return
            Clock.schedule_once(lambda *_: on_success(result), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _async_error(self, exc: Exception):
        if self.repository.unlocked and hasattr(self, "status_label"):
            self.status_label.text = self._status_text()
        self.popup("No se completó", str(exc))

    def lock(self, *, immediate=False):
        if not self.repository.unlocked:
            self.show_unlock()
            return
        self._stop_peer_services()
        Clock.unschedule(self._clear_clipboard)
        self._clear_clipboard()
        if immediate or not hasattr(self, "hero"):
            self._finish_lock()
            return
        self._play_sound("close")
        self._show_lock_transition()

    def _show_lock_transition(self):
        self.clear()
        page = ScrollView(do_scroll_x=False, bar_width=dp(4), scroll_y=1)
        outer = ResponsiveColumn(
            orientation="vertical",
            spacing=dp(14),
            size_hint=(None, None),
        )
        page.bind(width=lambda instance, value: setattr(outer, "width", value))
        outer.width = page.width
        outer.bind(minimum_height=outer.setter("height"))
        stage = ChestStage(opened=True, caption="CERRANDO Y PROTEGIENDO")
        outer.add_widget(stage)
        status = make_label(
            "Tus contraseñas y notas vuelven a quedar cifradas.",
            13,
            MUTED,
            False,
            42,
        )
        status.halign = "center"
        outer.add_widget(status)
        page.add_widget(outer)
        backdrop = VaultBackdrop()
        backdrop.add_widget(page)
        self.root_box.add_widget(backdrop)
        page.size = self.root_box.size
        outer.width = page.width
        outer._adapt_padding()
        Clock.schedule_once(lambda _dt: self.root_box.do_layout(), 0)
        Clock.schedule_once(
            lambda _dt: stage.chest.set_opened(
                False,
                animate=self._animations_enabled(),
                on_complete=self._finish_lock,
            ),
            0.08,
        )

    def _finish_lock(self):
        self.repository.lock()
        self.show_unlock()

    def on_pause(self):
        self.lock(immediate=True)
        return True

    def on_resume(self):
        return None

    def on_stop(self):
        self._stop_peer_services()
        self.repository.lock()
        self._clear_clipboard()
        self._remove_legacy_totp_qr()
