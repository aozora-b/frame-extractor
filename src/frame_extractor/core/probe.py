"""Membaca metadata video lewat ffprobe, dengan cadangan OpenCV."""

from __future__ import annotations

import json
import logging
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from .errors import MetadataError, UnsupportedVideoError, VideoNotFoundError
from .ffmpeg_tools import find_ffprobe
from .formats import is_video_file
from .models import VideoInfo
from .process import hidden_process_kwargs

log = logging.getLogger(__name__)

_OPENCV_CODECS = {
    "avc1": "h264",
    "h264": "h264",
    "x264": "h264",
    "hev1": "hevc",
    "hvc1": "hevc",
    "mp4v": "mpeg4",
    "vp09": "vp9",
    "vp80": "vp8",
    "av01": "av1",
    "mjpg": "mjpeg",
    "jpeg": "mjpeg",
}


def probe(path: Path) -> VideoInfo:
    """Baca metadata video. Melempar ``DomainError`` bila berkas tidak bisa dibaca."""

    path = Path(path).expanduser()
    if not path.exists():
        raise VideoNotFoundError(
            f"Berkas tidak ditemukan: {path.name}",
            detail=str(path),
            advice="Periksa apakah berkas dipindahkan atau namanya berubah.",
        )
    if not path.is_file():
        raise VideoNotFoundError(
            f"Bukan berkas: {path.name}",
            detail=str(path),
            advice="Pilih berkas video, bukan folder.",
        )
    if not is_video_file(path):
        raise UnsupportedVideoError(
            f"Format berkas tidak didukung: {path.suffix or 'tanpa ekstensi'}",
            detail=str(path),
            advice="Pilih berkas video seperti MP4, MKV, MOV, atau WebM.",
        )

    attempts: list[str] = []

    ffprobe = find_ffprobe()
    if ffprobe:
        try:
            return _probe_ffprobe(path, ffprobe)
        except UnsupportedVideoError:
            raise
        except (MetadataError, OSError, subprocess.SubprocessError, ValueError) as exc:
            attempts.append(f"ffprobe: {exc}")
            log.warning("ffprobe gagal untuk %s: %s", path, exc)
    else:
        attempts.append("ffprobe tidak ditemukan")

    try:
        return _probe_opencv(path)
    except UnsupportedVideoError:
        raise
    except Exception as exc:  # noqa: BLE001 - semua kegagalan berarti metadata tidak terbaca
        attempts.append(f"OpenCV: {exc}")
        log.warning("OpenCV gagal untuk %s: %s", path, exc)

    raise MetadataError(
        f"Metadata video tidak terbaca: {path.name}",
        detail="\n".join(attempts),
        advice=(
            "Pastikan berkas tidak rusak dan codec-nya didukung. "
            "Coba buka video di pemutar lain, atau pasang ffmpeg."
        ),
    )


def _parse_rate(value: object) -> float | None:
    try:
        rate = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None
    if not math.isfinite(rate) or rate <= 0:
        return None
    return rate


def _parse_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _parse_tag_duration(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (float(part) for part in parts)
    except ValueError:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _probe_ffprobe(path: Path, ffprobe: str) -> VideoInfo:
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_process_kwargs(),
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise MetadataError(
            "ffprobe tidak dapat membaca berkas.",
            detail=stderr[-1500:],
        )

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MetadataError("Keluaran ffprobe bukan JSON yang valid.", detail=str(exc)) from exc

    streams = data.get("streams") or []
    video_stream = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
            and not (stream.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )
    if video_stream is None:
        raise UnsupportedVideoError(
            f"Tidak ada aliran video di dalam {path.name}.",
            advice="Berkas ini mungkin hanya berisi audio atau gambar sampul.",
        )

    fmt = data.get("format") or {}
    tags = {str(key).upper(): value for key, value in (fmt.get("tags") or {}).items()}
    duration = (
        _parse_float(fmt.get("duration"))
        or _parse_float(video_stream.get("duration"))
        or _parse_tag_duration(tags.get("DURATION"))
    )
    fps = _parse_rate(video_stream.get("avg_frame_rate")) or _parse_rate(
        video_stream.get("r_frame_rate")
    )

    frame_count = 0
    try:
        raw_count = int(str(video_stream.get("nb_frames", "0")))
        if raw_count > 0:
            frame_count = raw_count
    except (TypeError, ValueError):
        pass

    if duration is None and fps and frame_count:
        duration = frame_count / fps
    if fps is None and duration and frame_count:
        fps = frame_count / duration
    if not duration or not fps:
        raise MetadataError(
            "Durasi atau frame rate video tidak terbaca.",
            detail=json.dumps(video_stream, ensure_ascii=False)[:1500],
        )
    if frame_count <= 0:
        frame_count = max(1, round(duration * fps))

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise MetadataError("Resolusi video tidak terbaca.")

    codec = str(video_stream.get("codec_name") or video_stream.get("codec_tag_string") or "?")

    warnings: list[str] = []
    avg_rate = _parse_rate(video_stream.get("avg_frame_rate"))
    real_rate = _parse_rate(video_stream.get("r_frame_rate"))
    if avg_rate and real_rate and abs(avg_rate - real_rate) > max(0.05, real_rate * 0.005):
        warnings.append(
            "Video ini tampaknya memiliki frame rate variabel (VFR); "
            "timestamp hasil ekstraksi bersifat perkiraan."
        )

    if duration > 2 * 3600:
        warnings.append("Video ini lebih dari 2 jam; ekstraksi bisa memakan waktu lama.")

    return VideoInfo(
        path=path,
        duration_s=float(duration),
        fps=float(fps),
        width=width,
        height=height,
        frame_count=int(frame_count),
        codec=codec,
        warnings=tuple(warnings),
    )


def _fourcc_to_text(value: float) -> str:
    number = int(value)
    if number <= 0:
        return "?"
    try:
        raw = number.to_bytes(4, "little", signed=False)
        text = raw.decode("ascii", errors="ignore")
    except (OverflowError, UnicodeDecodeError):
        return "?"
    text = "".join(char for char in text if char.isprintable()).strip("\x00").lower()
    return text or "?"


def _probe_opencv(path: Path) -> VideoInfo:
    try:
        import cv2
    except ImportError as exc:
        raise MetadataError(
            "OpenCV tidak terpasang, sehingga cadangan pembacaan metadata tidak tersedia.",
            detail=str(exc),
        ) from exc

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise MetadataError("OpenCV tidak dapat membuka berkas video ini.")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise MetadataError("OpenCV tidak dapat membaca frame pertama video ini.")
        if fps <= 0:
            raise MetadataError("Frame rate video tidak terbaca oleh OpenCV.")
        if frame_count <= 0:
            raise MetadataError("Jumlah frame video tidak terbaca oleh OpenCV.")
        duration = frame_count / fps
        if duration <= 0:
            raise MetadataError("Durasi video tidak terbaca oleh OpenCV.")
        if width <= 0 or height <= 0:
            height, width = frame.shape[:2]
        codec = _fourcc_to_text(capture.get(cv2.CAP_PROP_FOURCC))
        codec = _OPENCV_CODECS.get(codec, codec)
        return VideoInfo(
            path=path,
            duration_s=duration,
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count,
            codec=codec,
            warnings=(),
        )
    finally:
        capture.release()
