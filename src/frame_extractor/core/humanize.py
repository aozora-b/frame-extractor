"""Pemformatan angka untuk UI dan CLI.

Bahasa Indonesia tetap menjadi default agar keluaran CLI tidak berubah.
Antarmuka dapat meminta format Inggris dengan ``lang="en"``.
"""

from __future__ import annotations


def _english(lang: str) -> bool:
    return str(lang).lower().startswith("en")


def human_bytes(size: float, lang: str = "id") -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(max(0, size))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            text = f"{value:.1f}".rstrip("0").rstrip(".")
            if not _english(lang):
                text = text.replace(".", ",")
            return f"{text} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def human_duration(seconds: float, lang: str = "id") -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if _english(lang):
        if hours:
            return f"{hours} h {minutes:02d} min"
        if minutes:
            return f"{minutes} min {secs:02d} s"
        return f"{secs} s"
    if hours:
        return f"{hours} j {minutes:02d} mnt"
    if minutes:
        return f"{minutes} mnt {secs:02d} dtk"
    return f"{secs} dtk"


def eta_text(seconds: float | None, lang: str = "id") -> str:
    english = _english(lang)
    if seconds is None:
        return "calculating remaining time…" if english else "menghitung sisa waktu…"
    if seconds <= 0:
        return "almost done" if english else "hampir selesai"
    duration = human_duration(seconds, lang)
    return f"remaining {duration}" if english else f"sisa {duration}"
