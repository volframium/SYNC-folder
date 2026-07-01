"""File synchronization between paired folders."""

import os
import shutil
from datetime import datetime
from pathlib import Path

from config_manager import CONFIG_FILENAME, config_path, update_timestamp, write_config


def _iter_files(folder: Path) -> list[Path]:
    files: list[Path] = []
    if not folder.is_dir():
        return files

    for root, _dirs, names in os.walk(folder):
        root_path = Path(root)
        for name in names:
            file_path = root_path / name
            if file_path.name == CONFIG_FILENAME:
                continue
            files.append(file_path)
    return files


def _relative_to(folder: Path, file_path: Path) -> Path:
    return file_path.relative_to(folder)


def sync_folder(source: str | Path, destination: str | Path, source_timestamp: datetime) -> None:
    source_path = Path(source).resolve()
    dest_path = Path(destination).resolve()

    if not source_path.is_dir():
        raise FileNotFoundError(f"Source folder not found: {source_path}")
    if not dest_path.is_dir():
        raise FileNotFoundError(f"Destination folder not found: {dest_path}")

    source_files = {_relative_to(source_path, path) for path in _iter_files(source_path)}
    dest_files = {_relative_to(dest_path, path) for path in _iter_files(dest_path)}

    for relative in source_files:
        src = source_path / relative
        dst = dest_path / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for relative in dest_files - source_files:
        target = dest_path / relative
        if target.is_file():
            target.unlink()
        parent = target.parent
        while parent != dest_path and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    dest_config = config_path(dest_path)
    if dest_config.is_file():
        lines = dest_config.read_text(encoding="utf-8").splitlines()
        key = lines[0].strip() if lines else ""
        if key:
            write_config(dest_path, key, source_timestamp)
        else:
            update_timestamp(dest_path, source_timestamp)
    else:
        update_timestamp(dest_path, source_timestamp)
