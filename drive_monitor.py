"""Removable drive detection on Windows."""

import ctypes
import string
import threading
import time
from pathlib import Path

DRIVE_REMOVABLE = 2


def _get_drive_type(root: str) -> int:
    return ctypes.windll.kernel32.GetDriveTypeW(root)


def list_removable_drives() -> list[str]:
    drives: list[str] = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for index, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << index):
            root = f"{letter}:\\"
            if _get_drive_type(root) == DRIVE_REMOVABLE:
                drives.append(root)
    return drives


def find_config_folders_on_removable_drives(config_filename: str = "sync_config.txt") -> list[dict]:
    matches: list[dict] = []
    for drive in list_removable_drives():
        drive_path = Path(drive)
        try:
            for config_file in drive_path.rglob(config_filename):
                folder = config_file.parent
                matches.append(
                    {
                        "drive": drive,
                        "folder": str(folder.resolve()),
                        "config_file": str(config_file.resolve()),
                    }
                )
        except OSError:
            continue
    return matches


class DriveMonitor:
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._known_drives: set[str] = set()
        self._connected_callbacks: list = []
        self._disconnected_callbacks: list = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def on_drive_connected(self, callback) -> None:
        self._connected_callbacks.append(callback)

    def on_drive_disconnected(self, callback) -> None:
        self._disconnected_callbacks.append(callback)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._known_drives = set(list_removable_drives())
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            current = set(list_removable_drives())
            new_drives = current - self._known_drives
            removed_drives = self._known_drives - current
            self._known_drives = current

            for drive in sorted(removed_drives):
                for callback in self._disconnected_callbacks:
                    try:
                        callback(drive)
                    except Exception:
                        pass

            for drive in sorted(new_drives):
                time.sleep(0.5)
                for callback in self._connected_callbacks:
                    try:
                        callback(drive)
                    except Exception:
                        pass

            self._stop_event.wait(self.poll_interval)
