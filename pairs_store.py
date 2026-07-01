"""Persistent storage for registered sync pairs."""

import json
from pathlib import Path

APP_DIR = Path.home() / "AppData" / "Local" / "FolderSync"
PAIRS_FILE = APP_DIR / "pairs.json"


def _ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_pairs() -> list[dict]:
    _ensure_app_dir()
    if not PAIRS_FILE.is_file():
        return []

    try:
        data = json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    pairs = data.get("pairs", [])
    return [pair for pair in pairs if pair.get("key") and pair.get("pc_path")]


def save_pairs(pairs: list[dict]) -> None:
    _ensure_app_dir()
    PAIRS_FILE.write_text(
        json.dumps({"pairs": pairs}, indent=2),
        encoding="utf-8",
    )


def add_pair(key: str, pc_path: str) -> None:
    pairs = load_pairs()
    pc_path = str(Path(pc_path).resolve())

    pairs = [pair for pair in pairs if pair.get("key") != key]
    pairs.append({"key": key, "pc_path": pc_path})
    save_pairs(pairs)


def remove_pair(key: str) -> None:
    pairs = [pair for pair in load_pairs() if pair.get("key") != key]
    save_pairs(pairs)
