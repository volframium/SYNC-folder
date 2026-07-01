"""Configuration file management for folder sync pairs."""

import os
import secrets
import string
from datetime import datetime
from pathlib import Path

CONFIG_FILENAME = "sync_config.txt"
KEY_LENGTH = 16
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def generate_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(KEY_LENGTH))


def format_timestamp(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime(TIMESTAMP_FORMAT)


def parse_timestamp(value: str) -> datetime:
    value = value.strip()
    for fmt in (TIMESTAMP_FORMAT, "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid timestamp: {value!r}")


def config_path(folder: str | Path) -> Path:
    return Path(folder) / CONFIG_FILENAME


def read_config(folder: str | Path) -> dict | None:
    path = config_path(folder)
    if not path.is_file():
        return None

    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None

    key = lines[0].strip()
    if len(key) != KEY_LENGTH:
        return None

    try:
        timestamp = parse_timestamp(lines[1])
    except ValueError:
        return None

    return {"key": key, "timestamp": timestamp, "path": str(Path(folder).resolve())}


def write_config(folder: str | Path, key: str, timestamp: datetime | None = None) -> Path:
    folder_path = Path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    if timestamp is None:
        timestamp = datetime.now()

    path = config_path(folder_path)
    content = f"{key}\n{format_timestamp(timestamp)}\n"
    path.write_text(content, encoding="utf-8")
    return path


def update_timestamp(folder: str | Path, timestamp: datetime | None = None) -> bool:
    config = read_config(folder)
    if config is None:
        return False
    write_config(folder, config["key"], timestamp)
    return True


def find_newest_file_time(folder: str | Path) -> datetime | None:
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return None

    newest: datetime | None = None
    config_file = config_path(folder_path)

    for root, _dirs, files in os.walk(folder_path):
        for name in files:
            file_path = Path(root) / name
            if file_path == config_file:
                continue
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                ctime = datetime.fromtimestamp(file_path.stat().st_ctime)
                candidate = max(mtime, ctime)
                if newest is None or candidate > newest:
                    newest = candidate
            except OSError:
                continue

    return newest


def scan_and_update_config_timestamp(folder: str | Path) -> datetime | None:
    config = read_config(folder)
    if config is None:
        return None

    newest = find_newest_file_time(folder)
    timestamp = newest if newest is not None else config["timestamp"]
    write_config(folder, config["key"], timestamp)
    return timestamp
