"""System tray integration."""

import threading
from typing import Callable

import pystray
from PIL import Image

from app_paths import APP_NAME, resource_path


class TrayIcon:
    def __init__(
        self,
        *,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        image = Image.open(resource_path("app.ico"))
        menu = pystray.Menu(
            pystray.MenuItem("Show", self._handle_show, default=True),
            pystray.MenuItem("Exit", self._handle_quit),
        )
        self._icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            self._icon.notify(message, title)

    def _handle_show(self, _icon, _item) -> None:
        self._on_show()

    def _handle_quit(self, _icon, _item) -> None:
        self._on_quit()
