"""Cofre ilustrado en perspectiva: atlas gótico y transición con luz y profundidad.

El arte tiene volumen dibujado; no es un modelo 3D articulado. El atlas se carga
una sola vez y se recorta en la GPU, sin duplicar imágenes ni generar archivos.
"""
from __future__ import annotations

import math
from functools import lru_cache

from kivy.animation import Animation
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget

from .config import resource_root


@lru_cache(maxsize=1)
def chest_textures():
    atlas = CoreImage(str(resource_root() / "assets/cofre_atlas_gothic.png")).texture
    cell = atlas.height
    if atlas.width != 2 * cell:
        raise ValueError("El atlas del cofre debe tener dos celdas cuadradas.")
    return atlas.get_region(0, 0, cell, cell), atlas.get_region(cell, 0, cell, cell)


class Chest3D(Widget):
    opening = NumericProperty(0)

    def __init__(self, *, opened=False, **kwargs):
        super().__init__(**kwargs)
        self.opened = opened
        closed, opened_texture = chest_textures()
        with self.canvas:
            self._aura_color = Color(.44, .06, .72, .12)
            self._aura = Ellipse()
            self._ring_color = Color(.68, .39, .95, .26)
            self._ring = Line(ellipse=(0, 0, 0, 0), width=1)
            self._closed_color = Color(1, 1, 1, 1)
            self._closed = Rectangle(texture=closed)
            self._open_color = Color(1, 1, 1, 0)
            self._open = Rectangle(texture=opened_texture)
        self.bind(pos=self._draw, size=self._draw, opening=self._draw)
        self.opening = 1 if opened else 0
        self._draw()

    def _draw(self, *_):
        progress = max(0, min(1, self.opening))
        pulse = math.sin(math.pi * progress)
        side = max(0, min(self.width, self.height) * (.98 + .018 * pulse))
        center_x, center_y = self.x + self.width / 2, self.y + self.height / 2
        position = (center_x - side / 2, center_y - side / 2 + side * .008 * pulse)
        for sprite in (self._closed, self._open):
            sprite.pos, sprite.size = position, (side, side)
        self._closed_color.a = 1 - progress
        self._open_color.a = progress
        self._aura_color.a = .06 + .12 * progress + .10 * pulse
        self._aura.pos = (center_x - side * .42, center_y - side * .38)
        self._aura.size = (side * .84, side * .75)
        self._ring_color.a = .14 + .15 * progress
        self._ring.ellipse = (center_x - side * .46, center_y - side * .46,
                              side * .92, side * .18)

    def set_opened(self, opened: bool, *, animate=True, on_complete=None):
        Animation.cancel_all(self, "opening")
        self.opened = opened
        if not animate:
            self.opening = 1 if opened else 0
            if on_complete:
                on_complete()
            return
        animation = Animation(opening=1 if opened else 0,
                              duration=.86 if opened else .68, t="in_out_cubic")
        if on_complete:
            animation.bind(on_complete=lambda *_: on_complete())
        animation.start(self)
