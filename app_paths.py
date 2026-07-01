"""Application paths for development and PyInstaller builds."""

import sys
from pathlib import Path

APP_NAME = "SYNC"
APP_DIR = Path.home() / "AppData" / "Local" / "FolderSync"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def resource_path(name: str) -> Path:
    return app_root() / name


def executable_path() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return (Path(__file__).resolve().parent / "main.py").resolve()


def autostart_command() -> str:
    if is_frozen():
        return f'"{executable_path()}"'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        pythonw = Path(sys.executable)

    main_script = Path(__file__).resolve().parent / "main.py"
    return f'"{pythonw}" "{main_script}"'
