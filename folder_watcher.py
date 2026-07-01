"""Real-time folder monitoring with watchdog."""

import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config_manager import CONFIG_FILENAME, update_timestamp


class _SyncEventHandler(FileSystemEventHandler):
    def __init__(self, folder: str, debounce_seconds: float = 0.5):
        super().__init__()
        self.folder = str(Path(folder).resolve())
        self.debounce_seconds = debounce_seconds
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        return Path(path).name == CONFIG_FILENAME

    def _schedule_update(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._apply_update)
            self._timer.daemon = True
            self._timer.start()

    def _apply_update(self) -> None:
        update_timestamp(self.folder)

    def on_created(self, event) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_update()

    def on_modified(self, event) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_update()

    def on_deleted(self, event) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_update()

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        if self._should_ignore(event.src_path) or self._should_ignore(event.dest_path):
            return
        self._schedule_update()


class FolderWatcher:
    def __init__(self):
        self._observer = Observer()
        self._watched: set[str] = set()
        self._handlers: dict[str, _SyncEventHandler] = {}
        self._started = False

    def watch(self, folder: str) -> None:
        folder = str(Path(folder).resolve())
        if folder in self._watched or not Path(folder).is_dir():
            return

        handler = _SyncEventHandler(folder)
        self._observer.schedule(handler, folder, recursive=True)
        self._watched.add(folder)
        self._handlers[folder] = handler

        if not self._started:
            self._observer.start()
            self._started = True

    def unwatch(self, folder: str) -> None:
        folder = str(Path(folder).resolve())
        handler = self._handlers.pop(folder, None)
        if handler is None:
            return

        self._observer.unschedule(handler)
        self._watched.discard(folder)

    def refresh(self, folders: list[str]) -> None:
        desired = {str(Path(folder).resolve()) for folder in folders if Path(folder).is_dir()}

        for folder in list(self._watched - desired):
            self.unwatch(folder)

        for folder in desired - self._watched:
            self.watch(folder)

    def stop(self) -> None:
        if self._started:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._started = False
        self._watched.clear()
