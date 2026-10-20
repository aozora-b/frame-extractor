"""Aturan nama berkas yang aman, deterministik, dan tidak menimpa berkas lama."""

from __future__ import annotations

import math
import re
import string
from pathlib import Path

from .errors import InvalidOptionError, OutputNotWritableError

_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_TRAILING = re.compile(r"[ .]+$")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "CONIN$",
    "CONOUT$",
}

_ALLOWED_FIELDS = {"stem", "index", "time", "ext"}
_MAX_NAME_LENGTH = 180


def sanitize_stem(name: str, fallback: str = "video") -> str:
    """Bersihkan nama dasar agar aman di Windows, Linux, dan macOS."""

    cleaned = _FORBIDDEN.sub("_", name)
    cleaned = _TRAILING.sub("", cleaned).strip()
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:_MAX_NAME_LENGTH]


def sanitize_filename(name: str, fallback: str = "frame") -> str:
    """Bersihkan nama berkas lengkap; pemisah path tidak pernah lolos."""

    cleaned = _FORBIDDEN.sub("_", name)
    cleaned = _TRAILING.sub("", cleaned).strip()
    if not cleaned:
        cleaned = fallback
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:_MAX_NAME_LENGTH]


def format_time(seconds: float) -> str:
    """Ubah detik ke ``HH-MM-SS`` (titik dua diganti tanda hubung)."""

    if not math.isfinite(seconds):
        seconds = 0.0
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}-{minutes:02d}-{secs:02d}"


def validate_template(template: str) -> None:
    """Pastikan template hanya memakai placeholder yang dikenal dan bisa dirender."""

    if not template or not template.strip():
        raise InvalidOptionError("Pola nama berkas tidak boleh kosong.")

    formatter = string.Formatter()
    try:
        fields = [field for _, field, _, _ in formatter.parse(template) if field]
    except ValueError as exc:
        raise InvalidOptionError(f"Pola nama berkas tidak valid: {exc}") from exc

    if not fields:
        raise InvalidOptionError("Pola nama berkas harus memuat {index} dan {ext}.")

    unknown = sorted({field.split(".")[0].split("[")[0] for field in fields} - _ALLOWED_FIELDS)
    if unknown:
        raise InvalidOptionError(
            "Pola nama berkas memakai placeholder yang tidak dikenal: "
            + ", ".join("{" + item + "}" for item in unknown)
            + ". Gunakan {stem}, {index}, {time}, dan {ext}."
        )

    if "index" not in fields:
        raise InvalidOptionError("Pola nama berkas harus memuat {index} agar urutan konsisten.")
    if "ext" not in fields:
        raise InvalidOptionError("Pola nama berkas harus memuat {ext}.")

    try:
        formatter.format(
            template,
            stem="contoh",
            index=1,
            time="00-00-00",
            ext="png",
        )
    except (ValueError, KeyError, IndexError) as exc:
        raise InvalidOptionError(f"Pola nama berkas tidak dapat dirender: {exc}") from exc


def build_name(stem: str, index: int, ts: float, ext: str, template: str) -> str:
    """Bangun nama berkas dari template. ``index`` sudah dimulai dari 1."""

    if index < 1:
        raise ValueError("index harus dimulai dari 1")
    ext = ext.lower().lstrip(".")
    if ext not in ("png", "jpg"):
        raise InvalidOptionError(f"Ekstensi keluaran tidak didukung: {ext!r}.")

    validate_template(template)
    rendered = template.format(
        stem=sanitize_stem(stem),
        index=index,
        time=format_time(ts),
        ext=ext,
    )
    safe = sanitize_filename(rendered)
    if not safe.lower().endswith(f".{ext}"):
        safe = f"{safe}.{ext}"
    if len(safe) > _MAX_NAME_LENGTH:
        suffix = f".{ext}"
        safe = safe[: _MAX_NAME_LENGTH - len(suffix)].rstrip(" .") + suffix
    return safe


def unique_path(directory: Path, filename: str) -> Path:
    """Kembalikan path yang belum ada; tambahkan ``-1``, ``-2``, ... bila perlu."""

    target = directory / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    for counter in range(1, 100_000):
        candidate = directory / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
    raise OutputNotWritableError(
        "Terlalu banyak nama berkas yang bentrok.",
        advice="Pilih folder keluaran lain atau hapus hasil lama.",
    )
