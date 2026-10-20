"""Pemilih mesin ekstraksi: ffmpeg lebih dulu, OpenCV sebagai cadangan."""

from __future__ import annotations

import logging
from typing import Literal

from .errors import DomainError, EngineUnavailableError, ExtractionFailedError
from .extract_common import CancelCallback, ProgressCallback
from .extract_ffmpeg import extract_ffmpeg
from .extract_opencv import extract_opencv
from .ffmpeg_tools import find_ffmpeg
from .models import ExtractOptions, FrameResult, VideoInfo

log = logging.getLogger(__name__)

Engine = Literal["auto", "ffmpeg", "opencv"]


def extract(
    info: VideoInfo,
    opt: ExtractOptions,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
    engine: Engine = "auto",
) -> list[FrameResult]:
    """Ekstrak frame. ``engine="auto"`` mencoba ffmpeg lalu OpenCV.

    Bila dibatalkan, fungsi mengembalikan frame yang sudah tersimpan (bukan
    melempar exception), sehingga pemanggil bisa melaporkan hasil parsial.
    """

    if engine not in ("auto", "ffmpeg", "opencv"):
        raise ValueError(f"Mesin tidak dikenal: {engine!r}")
    should_cancel = should_cancel or (lambda: False)
    errors: list[DomainError] = []

    if engine in ("auto", "ffmpeg"):
        if find_ffmpeg():
            try:
                return extract_ffmpeg(info, opt, on_progress, should_cancel)
            except ExtractionFailedError as exc:
                if exc.partial_results:
                    raise
                if should_cancel():
                    return []
                errors.append(exc)
                log.warning("ffmpeg gagal, mencoba OpenCV: %s", exc)
                if engine == "ffmpeg":
                    raise
            except EngineUnavailableError as exc:
                errors.append(exc)
                if engine == "ffmpeg":
                    raise
        else:
            errors.append(
                EngineUnavailableError(
                    "ffmpeg tidak ditemukan.",
                    advice="Pasang ffmpeg, atau gunakan mesin OpenCV yang ikut terpasang.",
                )
            )
            if engine == "ffmpeg":
                raise errors[-1]

    if engine in ("auto", "opencv"):
        try:
            return extract_opencv(info, opt, on_progress, should_cancel)
        except ExtractionFailedError as exc:
            if exc.partial_results:
                raise
            errors.append(exc)
        except EngineUnavailableError as exc:
            errors.append(exc)

    if not errors:
        raise EngineUnavailableError(
            "Tidak ada mesin ekstraksi yang tersedia.",
            advice="Pasang ffmpeg atau OpenCV, lalu jalankan ulang aplikasi.",
        )

    if len(errors) == 1:
        raise errors[0]

    detail = "\n\n".join(
        f"[{type(error).__name__}] {error.message}"
        + (f"\n{error.detail}" if error.detail else "")
        for error in errors
    )
    raise ExtractionFailedError(
        "Tidak ada mesin yang berhasil mengekstrak video ini.",
        detail=detail,
        advice=(
            "Codec mungkin tidak didukung. Coba konversi video ke MP4/H.264, "
            "atau periksa apakah berkas benar-benar utuh."
        ),
    )
