"""Mesin cadangan: OpenCV, dengan kontrak keluaran yang sama seperti ffmpeg."""

from __future__ import annotations

import logging
from pathlib import Path

from .errors import EngineUnavailableError, ExtractionFailedError
from .extract_common import (
    CancelCallback,
    ProgressCallback,
    ProgressReporter,
    ensure_disk_space,
    prepare_output_dir,
)
from .models import ExtractOptions, FrameResult, VideoInfo
from .naming import build_name, sanitize_stem, unique_path
from .plan import estimate_output_bytes, plan_points

log = logging.getLogger(__name__)


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - hanya bila instalasi tidak lengkap
        raise EngineUnavailableError(
            "OpenCV tidak terpasang, sehingga mesin cadangan tidak tersedia.",
            detail=str(exc),
            advice="Pasang ulang aplikasi, atau pasang ffmpeg dan gunakan mesin utama.",
        ) from exc
    return cv2


def _save_frame(cv2, frame, destination: Path, opt: ExtractOptions) -> int:
    if opt.fmt == "png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 6]
        extension = ".png"
    else:
        params = [cv2.IMWRITE_JPEG_QUALITY, max(1, min(100, opt.quality))]
        extension = ".jpg"

    ok, buffer = cv2.imencode(extension, frame, params)
    if not ok:
        raise ExtractionFailedError(
            f"Gambar tidak dapat dikodekan sebagai {extension.upper()[1:]}.",
            advice="Coba format PNG, atau periksa ruang disk.",
        )
    try:
        destination.write_bytes(buffer.tobytes())
    except OSError as exc:
        raise ExtractionFailedError(
            f"Hasil tidak dapat disimpan: {destination.name}",
            detail=str(exc),
            advice="Periksa izin folder dan ruang disk.",
        ) from exc
    return destination.stat().st_size


def extract_opencv(
    info: VideoInfo,
    opt: ExtractOptions,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> list[FrameResult]:
    """Ekstrak frame dengan OpenCV, membaca video secara berurutan."""

    on_progress = on_progress or (lambda done, total, ts: None)
    should_cancel = should_cancel or (lambda: False)
    cv2 = _import_cv2()

    points = plan_points(info, opt)
    total = len(points)
    out_dir = prepare_output_dir(info, opt)
    ensure_disk_space(out_dir, estimate_output_bytes(info, opt, total))
    reporter = ProgressReporter(on_progress, total)
    reporter(0, points[0], force=True)

    capture = cv2.VideoCapture(str(info.path))
    results: list[FrameResult] = []
    cancelled = False

    try:
        if not capture.isOpened():
            raise EngineUnavailableError(
                f"OpenCV tidak dapat membuka {info.path.name}.",
                detail=f"Codec: {info.codec}",
                advice=(
                    "Codec ini mungkin tidak didukung OpenCV. "
                    "Pasang ffmpeg atau konversi video ke MP4/H.264."
                ),
            )

        fps = float(capture.get(cv2.CAP_PROP_FPS) or info.fps or 0)
        if fps <= 0:
            raise EngineUnavailableError(
                "OpenCV tidak dapat membaca frame rate video.",
                advice="Gunakan ffmpeg atau konversi video terlebih dahulu.",
            )

        start = max(0.0, min(float(opt.start_s), info.duration_s))
        if start > 1.0:
            capture.set(cv2.CAP_PROP_POS_MSEC, (start - 1.0) * 1000.0)

        fallback_frame = max(0, int(capture.get(cv2.CAP_PROP_POS_FRAMES) or 0))
        last_t = -1.0
        next_index = 0
        stem = sanitize_stem(info.path.stem)

        while next_index < total:
            if should_cancel():
                cancelled = True
                break

            ok, frame = capture.read()
            if not ok or frame is None:
                break

            pos_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            timestamp = pos_ms / 1000.0 if pos_ms > 0 else fallback_frame / fps
            if timestamp < last_t - 0.05:
                timestamp = fallback_frame / fps
            last_t = timestamp
            fallback_frame += 1

            # Ambil semua titik yang jatuh pada frame ini (interval bisa lebih rapat
            # daripada frame rate sumber).
            while next_index < total and points[next_index] <= timestamp + 0.5 / fps:
                ts = points[next_index]
                filename = build_name(stem, next_index + 1, ts, opt.fmt, opt.template)
                destination = unique_path(out_dir, filename)
                size = _save_frame(cv2, frame, destination, opt)
                results.append(
                    FrameResult(
                        path=destination,
                        timestamp_s=ts,
                        index=next_index + 1,
                        size_bytes=size,
                    )
                )
                next_index += 1
                reporter(next_index, ts)
                if should_cancel():
                    cancelled = True
                    break

            if cancelled:
                break

        if cancelled:
            reporter(len(results), points[-1] if points else 0.0, force=True)
            log.info("Ekstraksi OpenCV dibatalkan; %d frame tersimpan.", len(results))
            return results

        if len(results) < total:
            raise ExtractionFailedError(
                f"Hanya {len(results)} dari {total} frame yang berhasil dibaca.",
                detail=f"fps={fps:.3f}, codec={info.codec}",
                advice=(
                    "Video mungkin lebih pendek dari metadata atau memakai codec yang "
                    "tidak didukung. Coba ffmpeg atau konversi video ke MP4/H.264."
                ),
                partial_results=results,
            )

        reporter(total, points[-1], force=True)
        log.info("Selesai (OpenCV): %d frame dari %s", len(results), info.path.name)
        return results

    finally:
        capture.release()
