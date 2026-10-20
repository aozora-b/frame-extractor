"""Perhitungan titik sampel untuk ketiga mode pengambilan."""

from __future__ import annotations

import math

from .errors import PlanError
from .models import ExtractOptions, VideoInfo

MAX_FRAMES = 200_000
_EPS = 1e-9


def _span(info: VideoInfo, opt: ExtractOptions) -> tuple[float, float]:
    duration = float(info.duration_s)
    if not math.isfinite(duration) or duration <= 0:
        raise PlanError(
            "Durasi video tidak terbaca, sehingga titik sampel tidak dapat dihitung.",
            advice="Coba berkas video lain atau periksa apakah berkas rusak.",
        )

    start = max(0.0, min(float(opt.start_s), duration))
    end = duration if opt.end_s is None else min(float(opt.end_s), duration)
    if start >= duration - _EPS:
        raise PlanError(
            "Waktu mulai berada di luar durasi video.",
            advice=f"Durasi video ini {duration:.1f} detik; turunkan waktu mulai.",
        )
    if end - start <= _EPS:
        raise PlanError(
            "Rentang waktu tidak menyisakan satu frame pun.",
            advice="Perlebar rentang waktu atau turunkan waktu mulai.",
        )
    return start, end


def plan_points(info: VideoInfo, opt: ExtractOptions) -> list[float]:
    """Hasilkan daftar timestamp (detik) yang akan diambil, terurut menaik.

    - ``interval``: satu frame tiap ``interval_s`` mulai dari ``start_s``.
    - ``count``: ``frame_total`` frame tersebar merata pada rentang.
    - ``range``: satu frame tiap ``interval_s`` di dalam ``[start_s, end_s)``.
    """

    start, end = _span(info, opt)
    span = end - start

    if opt.mode == "count":
        count = int(opt.frame_total)
        if count < 1:
            raise PlanError("Jumlah frame harus minimal 1.")
        if count > MAX_FRAMES:
            raise PlanError(
                f"Jumlah frame terlalu banyak ({count:,}). Batas aman {MAX_FRAMES:,}.",
                advice="Kurangi jumlah frame yang diminta.",
            )
        step = span / count
        times = [start + i * step for i in range(count)]
    else:
        interval = float(opt.interval_s)
        if interval <= 0:
            raise PlanError("Interval harus lebih besar dari 0 detik.")
        count = int(math.floor((span - _EPS) / interval)) + 1
        if count > MAX_FRAMES:
            raise PlanError(
                f"Interval terlalu rapat: akan menghasilkan {count:,} frame "
                f"(batas {MAX_FRAMES:,}).",
                advice="Perbesar interval atau perkecil rentang waktu.",
            )
        times = [start + i * interval for i in range(count)]

    # Jaga presisi floating point: buang titik yang (karena pembulatan) menyentuh akhir.
    times = [t for t in times if t < end - _EPS]
    if not times:
        raise PlanError(
            "Tidak ada frame yang bisa diambil dengan setelan ini.",
            advice="Perlebar rentang waktu atau perkecil interval.",
        )
    # Pastikan benar-benar terurut dan unik.
    result: list[float] = []
    for t in times:
        if not result or t > result[-1] + 1e-9:
            result.append(round(t, 6))
    if not result:
        raise PlanError("Tidak ada frame yang bisa diambil dengan setelan ini.")
    return result


def estimate_output_bytes(info: VideoInfo, opt: ExtractOptions, count: int) -> int:
    """Perkiraan kasar ukuran hasil (PNG ~1,5 byte/piksel sesuai spesifikasi)."""

    pixels = max(1, int(info.width) * int(info.height))
    per_pixel = 1.5 if opt.fmt == "png" else 0.15 + 0.35 * (opt.quality / 100)
    return max(count, 1) * int(pixels * per_pixel)
