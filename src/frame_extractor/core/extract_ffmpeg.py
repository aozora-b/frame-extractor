"""Mesin ekstraksi utama: satu proses ffmpeg, progres dari stderr, bisa dibatalkan."""

from __future__ import annotations

import contextlib
import logging
import queue
import subprocess
import threading
import time
from pathlib import Path

from .errors import EngineUnavailableError, ExtractionFailedError
from .extract_common import (
    CancelCallback,
    ProgressCallback,
    ProgressReporter,
    cleanup_temp_dir,
    ensure_disk_space,
    finalize_temp_frames,
    make_temp_dir,
    prepare_output_dir,
)
from .ffmpeg_tools import find_ffmpeg
from .models import ExtractOptions, FrameResult, VideoInfo
from .plan import estimate_output_bytes, plan_points
from .process import hidden_process_kwargs

log = logging.getLogger(__name__)

_PROGRESS_KEYS = {
    "frame",
    "fps",
    "stream_0_0_q",
    "bitrate",
    "total_size",
    "out_time_us",
    "out_time_ms",
    "out_time",
    "dup_frames",
    "drop_frames",
    "speed",
    "progress",
}


def jpeg_quality_to_qscale(quality: int) -> int:
    """Petakan kualitas 1–100 ke skala ffmpeg 2–31 (kebalikan)."""

    quality = max(1, min(100, int(quality)))
    return max(2, min(31, round(31 - (quality - 1) * 29 / 99)))


def _build_command(
    ffmpeg: str,
    info: VideoInfo,
    opt: ExtractOptions,
    points: list[float],
    temp_dir: Path,
) -> tuple[list[str], float, float]:
    start = max(0.0, min(float(opt.start_s), info.duration_s))
    end = info.duration_s if opt.end_s is None else min(float(opt.end_s), info.duration_s)
    span = max(0.001, end - start)
    fps = len(points) / span if opt.mode == "count" else 1.0 / opt.interval_s

    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-nostats",
        "-stats_period",
        "0.2",
        "-progress",
        "pipe:2",
    ]
    if start > 0:
        command += ["-ss", f"{start:.6f}"]
    command += [
        "-i",
        str(info.path),
        "-t",
        f"{span:.6f}",
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-vf",
        f"fps={fps:.9f}",
        "-frames:v",
        str(len(points)),
    ]
    if opt.fmt == "png":
        command += ["-compression_level", "6"]
    else:
        command += ["-q:v", str(jpeg_quality_to_qscale(opt.quality))]
    command += [
        "-start_number",
        "1",
        "-y",
        str(temp_dir / f"frame_%06d.{opt.fmt}"),
    ]
    return command, start, span


def _reader(stream, output: queue.Queue[str | None]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output.put(line)
    finally:
        output.put(None)
        with contextlib.suppress(OSError):
            stream.close()


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(OSError):
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            log.error("Proses ffmpeg tidak berhenti setelah kill.")


def extract_ffmpeg(
    info: VideoInfo,
    opt: ExtractOptions,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> list[FrameResult]:
    """Ekstrak frame dengan ffmpeg. Hasil parsial dipertahankan bila dibatalkan/gagal."""

    on_progress = on_progress or (lambda done, total, ts: None)
    should_cancel = should_cancel or (lambda: False)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise EngineUnavailableError(
            "ffmpeg tidak ditemukan.",
            advice=(
                "Pasang ffmpeg dan pastikan ada di PATH, atau gunakan mesin OpenCV. "
                "Versi rilis aplikasi sudah menyertakan ffmpeg."
            ),
        )

    points = plan_points(info, opt)
    total = len(points)
    out_dir = prepare_output_dir(info, opt)
    ensure_disk_space(out_dir, estimate_output_bytes(info, opt, total))
    temp_dir = make_temp_dir(out_dir)
    reporter = ProgressReporter(on_progress, total)
    reporter(0, points[0], force=True)

    command, _start, _span = _build_command(ffmpeg, info, opt, points, temp_dir)
    log.info("Menjalankan ffmpeg untuk %s (%d frame)", info.path.name, total)

    process: subprocess.Popen | None = None
    cancelled = False
    error_lines: list[str] = []
    results: list[FrameResult] = []

    try:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **hidden_process_kwargs(),
            )
        except OSError as exc:
            raise EngineUnavailableError(
                "ffmpeg tidak dapat dijalankan.",
                detail=str(exc),
                advice="Pastikan ffmpeg tidak diblokir antivirus dan berkasnya lengkap.",
            ) from exc

        assert process.stderr is not None
        messages: queue.Queue[str | None] = queue.Queue()
        reader_thread = threading.Thread(
            target=_reader, args=(process.stderr, messages), daemon=True
        )
        reader_thread.start()

        done = 0
        announced = 0

        while True:
            if should_cancel():
                cancelled = True
                _stop_process(process)
                break

            while True:
                try:
                    line = messages.get_nowait()
                except queue.Empty:
                    break
                if line is None:
                    break
                text = line.strip()
                if not text:
                    continue
                key, _, value = text.partition("=")
                if key in _PROGRESS_KEYS:
                    if key == "frame":
                        try:
                            done = int(value)
                        except ValueError:
                            done = done
                    elif key == "progress" and value.strip() == "end":
                        done = total
                    if key == "frame" and done != announced:
                        announced = done
                        ts = (
                            points[min(done - 1, total - 1)]
                            if done > 0
                            else points[0]
                        )
                        reporter(done, ts)
                else:
                    error_lines.append(text)
                    if len(error_lines) > 40:
                        del error_lines[:-40]

            if process.poll() is not None:
                break
            time.sleep(0.03)

        try:
            return_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _stop_process(process)
            return_code = process.returncode
        reader_thread.join(timeout=3)

        # Ambil sisa baris yang belum sempat diproses.
        while True:
            try:
                line = messages.get_nowait()
            except queue.Empty:
                break
            if line is None:
                break
            text = line.strip()
            if not text:
                continue
            key, _, value = text.partition("=")
            if key == "frame":
                with contextlib.suppress(ValueError):
                    done = int(value)
            elif key not in _PROGRESS_KEYS:
                error_lines.append(text)

        results = finalize_temp_frames(temp_dir, opt.fmt, points, info, opt, out_dir)

        if cancelled:
            final_ts = points[-1] if points else 0.0
            reporter(len(results), final_ts, force=True)
            log.info("Ekstraksi dibatalkan; %d frame tersimpan.", len(results))
            return results

        if return_code != 0:
            detail = "\n".join(error_lines[-25:]) or f"Kode keluar ffmpeg: {return_code}"
            raise ExtractionFailedError(
                f"ffmpeg berhenti dengan kode {return_code}.",
                detail=detail,
                advice=(
                    "Codec mungkin tidak didukung. Aplikasi akan mencoba mesin OpenCV; "
                    "bila tetap gagal, coba konversi video ke MP4/H.264."
                ),
                partial_results=results,
            )

        if len(results) < total:
            raise ExtractionFailedError(
                f"Hanya {len(results)} dari {total} frame yang berhasil dibuat.",
                detail="\n".join(error_lines[-25:]),
                advice=(
                    "Video mungkin lebih pendek dari metadata, atau codec-nya bermasalah. "
                    "Coba kurangi jumlah frame atau gunakan mesin OpenCV."
                ),
                partial_results=results,
            )

        reporter(total, points[-1], force=True)
        log.info("Selesai: %d frame dari %s", len(results), info.path.name)
        return results[:total]

    finally:
        if process is not None and process.poll() is None:
            _stop_process(process)
        cleanup_temp_dir(temp_dir)


__all__ = ["extract_ffmpeg", "jpeg_quality_to_qscale"]
