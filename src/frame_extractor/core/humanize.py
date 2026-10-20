"""Pemformatan angka untuk UI dan CLI (Bahasa Indonesia)."""

from __future__ import annotations


def human_bytes(size: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(0, size))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            text = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{text.replace('.', ',')} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def human_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} j {minutes:02d} mnt"
    if minutes:
        return f"{minutes} mnt {secs:02d} dtk"
    return f"{secs} dtk"


def eta_text(seconds: float | None) -> str:
    if seconds is None:
        return "menghitung sisa waktu…"
    if seconds <= 0:
        return "hampir selesai"
    return f"sisa {human_duration(seconds)}"
