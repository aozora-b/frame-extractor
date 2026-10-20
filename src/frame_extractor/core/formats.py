"""Daftar format video yang diterima dan pemindaian folder."""

from __future__ import annotations

import os
from pathlib import Path

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".m4v",
        ".mkv",
        ".mov",
        ".webm",
        ".avi",
        ".wmv",
        ".flv",
        ".mpg",
        ".mpeg",
        ".mts",
        ".m2ts",
        ".ts",
        ".3gp",
        ".3g2",
        ".ogv",
        ".ogg",
        ".asf",
        ".vob",
        ".f4v",
        ".mxf",
    }
)

FILE_DIALOG_FILTER = (
    "Berkas video (*.mp4 *.m4v *.mkv *.mov *.webm *.avi *.wmv *.flv *.mpg *.mpeg "
    "*.mts *.m2ts *.ts *.3gp *.3g2 *.ogv *.ogg *.asf *.vob *.f4v *.mxf);;Semua berkas (*)"
)


def is_video_file(path: Path) -> bool:
    """True bila ekstensi berkas termasuk format video yang didukung."""

    return path.suffix.lower() in VIDEO_EXTENSIONS


def scan_folder(folder: Path) -> list[Path]:
    """Cari video di dalam folder (termasuk subfolder), terurut dan tanpa duplikat."""

    found: list[Path] = []
    seen: set[str] = set()
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files, key=str.casefold):
            path = Path(root) / name
            if not is_video_file(path):
                continue
            key = os.path.normcase(str(path.resolve()))
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found
