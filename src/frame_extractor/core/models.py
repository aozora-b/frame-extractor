"""Tipe data yang menjadi kontrak antar-modul."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .errors import InvalidOptionError

Mode = Literal["interval", "count", "range"]
Format = Literal["png", "jpg"]


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    duration_s: float
    fps: float
    width: int
    height: int
    frame_count: int
    codec: str
    # Bidang tambahan yang tidak mengubah kontrak wajib: dipakai untuk peringatan
    # VFR dan informasi yang tidak selalu tersedia dari kontainer.
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}"


@dataclass(frozen=True)
class ExtractOptions:
    mode: Mode
    interval_s: float = 1.0
    frame_total: int = 30
    start_s: float = 0.0
    end_s: float | None = None
    fmt: Format = "png"
    quality: int = 95
    out_dir: Path | None = None
    template: str = "{stem}_{index:06d}_{time}.{ext}"

    def __post_init__(self) -> None:
        if self.mode not in ("interval", "count", "range"):
            raise InvalidOptionError(f"Mode pengambilan tidak dikenal: {self.mode!r}.")
        if self.fmt not in ("png", "jpg"):
            raise InvalidOptionError(f"Format keluaran tidak dikenal: {self.fmt!r}.")
        if self.start_s < 0:
            raise InvalidOptionError("Waktu mulai tidak boleh negatif.")
        if self.end_s is not None and self.end_s <= self.start_s:
            raise InvalidOptionError("Waktu selesai harus lebih besar dari waktu mulai.")
        if self.mode in ("interval", "range") and self.interval_s <= 0:
            raise InvalidOptionError("Interval harus lebih besar dari 0 detik.")
        if self.mode == "count" and self.frame_total < 1:
            raise InvalidOptionError("Jumlah frame harus minimal 1.")
        if not 1 <= self.quality <= 100:
            raise InvalidOptionError("Kualitas JPG harus di antara 1 dan 100.")
        # Impor lokal agar pesan galat template tetap satu sumber.
        from .naming import validate_template

        validate_template(self.template)


@dataclass(frozen=True)
class FrameResult:
    path: Path
    timestamp_s: float
    index: int
    size_bytes: int
