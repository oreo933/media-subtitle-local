from __future__ import annotations

from pathlib import Path


def scan_video_files(folder: str | Path, extensions: tuple[str, ...]) -> list[Path]:
    root = Path(folder)
    if not root.exists() or not root.is_dir():
        return []

    ext_set = {e.lower() for e in extensions}
    files = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in ext_set
    ]
    files.sort(key=lambda x: x.name.lower())
    return files
