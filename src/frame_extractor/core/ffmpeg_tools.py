"""Menemukan ffmpeg/ffprobe: bawaan aplikasi, env var, atau PATH."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_TOOL_NAMES = {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []

    env_dir = os.environ.get("FRAME_EXTRACTOR_FFMPEG_DIR")
    if env_dir:
        dirs.append(Path(env_dir).expanduser())

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(Path(meipass) / "ffmpeg" / "bin")
        dirs.append(Path(sys.executable).parent / "ffmpeg" / "bin")

    # Dari sumber: <root>/src/frame_extractor/core/ffmpeg_tools.py
    project_root = Path(__file__).resolve().parents[3]
    dirs.append(project_root / "third_party" / "ffmpeg" / "bin")

    return dirs


def _env_tool_path(tool: str) -> Path | None:
    key = "FRAME_EXTRACTOR_FFMPEG" if tool == "ffmpeg" else "FRAME_EXTRACTOR_FFPROBE"
    raw = os.environ.get(key)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_dir():
        path = path / (Path(_TOOL_NAMES[tool]).with_suffix(".exe" if os.name == "nt" else ""))
    return path if path.is_file() else None


def find_tool(tool: str) -> str | None:
    """Kembalikan path absolut ke ffmpeg/ffprobe, atau None."""

    if tool not in _TOOL_NAMES:
        raise ValueError(f"Alat tidak dikenal: {tool}")

    override = _env_tool_path(tool)
    if override:
        return str(override)

    filename = tool + (".exe" if os.name == "nt" else "")
    for directory in _candidate_dirs():
        candidate = directory / filename
        if candidate.is_file():
            return str(candidate)

    found = shutil.which(tool)
    return found


def find_ffmpeg() -> str | None:
    return find_tool("ffmpeg")


def find_ffprobe() -> str | None:
    return find_tool("ffprobe")


def ffmpeg_available() -> bool:
    return find_ffmpeg() is not None
