"""Acceso explícito a archivos elegidos; Android usa Storage Access Framework."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def open_selected(value: str, mode: str):
    if not value.startswith("content://"):
        with Path(value).open(mode) as stream:
            yield stream
        return
    from jnius import autoclass
    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    uri = autoclass("android.net.Uri").parse(value)
    # ACTION_CREATE_DOCUMENT devuelve un destino nuevo, no una ruta arbitraria.
    descriptor = activity.getContentResolver().openFileDescriptor(uri, "r" if mode == "rb" else "w")
    if descriptor is None:
        raise OSError("No se pudo abrir el archivo elegido.")
    try:
        fd = descriptor.detachFd()
    finally:
        descriptor.close()
    with os.fdopen(fd, "rb" if mode == "rb" else "wb") as stream:
        yield stream


def selected_details(value: str) -> tuple[str, int]:
    if not value.startswith("content://"):
        path = Path(value)
        return path.name, path.stat().st_size
    from jnius import autoclass
    resolver = autoclass("org.kivy.android.PythonActivity").mActivity.getContentResolver()
    cursor = resolver.query(autoclass("android.net.Uri").parse(value), None, None, None, None)
    try:
        if cursor is None or not cursor.moveToFirst():
            raise OSError("No se pudo conocer el tamaño del archivo.")
        name_index = cursor.getColumnIndex("_display_name")
        size_index = cursor.getColumnIndex("_size")
        if size_index < 0 or cursor.isNull(size_index):
            raise OSError("Descarga primero el archivo: el proveedor no informa su tamaño.")
        return (str(cursor.getString(name_index)) if name_index >= 0 else "archivo.bin", int(cursor.getLong(size_index)))
    finally:
        if cursor is not None:
            cursor.close()


def android_pick(*, save: bool, name: str, callback):
    from android import activity
    from android.runnable import run_on_ui_thread
    from jnius import autoclass
    from kivy.clock import Clock

    request = 4357
    def result(request_code, result_code, intent):
        if request_code != request:
            return
        def deliver(_dt):
            activity.unbind(on_activity_result=result)
            value = str(intent.getData().toString()) if result_code == -1 and intent is not None else ""
            callback(value)
        Clock.schedule_once(deliver, 0)

    activity.bind(on_activity_result=result)
    @run_on_ui_thread
    def launch():
        Intent = autoclass("android.content.Intent")
        intent = Intent(Intent.ACTION_CREATE_DOCUMENT if save else Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("application/octet-stream" if save else "*/*")
        if save:
            intent.putExtra(Intent.EXTRA_TITLE, name)
        autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(intent, request)
    try:
        launch()
    except Exception:
        activity.unbind(on_activity_result=result)
        raise
