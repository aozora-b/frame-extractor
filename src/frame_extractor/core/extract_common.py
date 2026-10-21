"""Bagian ekstraksi yang dipakai bersama oleh mesin ffmpeg dan OpenCV."""

from __future__ import annotations

import contextlib
import logging
import math
import os
import re
import secrets
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from .errors import (
    InsufficientDiskSpaceError,
    OutputNotWritableError,
)
from .humanize import human_bytes
from .models import ExtractOptions, FrameResult, VideoInfo
from .naming import build_name, sanitize_stem, unique_path

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


def prepare_output_dir(info: VideoInfo, opt: ExtractOptions) -> Path:
    """Tentukan, buat, dan uji-tulis folder keluaran."""

    out_dir = Path(opt.out_dir).expanduser() if opt.out_dir else info.path.parent
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputNotWritableError(
            f"Folder keluaran tidak dapat dibuat: {out_dir}",
            detail=str(exc),
            advice="Pilih folder lain yang Anda punya izin menulisnya.",
        ) from exc

    if not out_dir.is_dir():
        raise OutputNotWritableError(
            f"Folder keluaran bukan folder: {out_dir}",
            advice="Pilih folder, bukan berkas.",
        )

    probe_file: str | None = None
    try:
        handle, probe_file = tempfile.mkstemp(prefix=".frame-extractor-", dir=out_dir)
        os.close(handle)
    except OSError as exc:
        raise OutputNotWritableError(
            f"Folder keluaran tidak dapat ditulis: {out_dir}",
            detail=str(exc),
            advice="Pilih folder lain, atau ubah izin folder tersebut.",
        ) from exc
    finally:
        if probe_file:
            with contextlib.suppress(OSError):
                os.unlink(probe_file)

    return out_dir.resolve()


def ensure_disk_space(out_dir: Path, needed_bytes: int) -> None:
    """Peringatkan lebih awal bila ruang disk tidak mencukupi."""

    try:
        usage = shutil.disk_usage(out_dir)
    except OSError:
        return
    buffer_bytes = 20 * 1024 * 1024
    if needed_bytes + buffer_bytes > usage.free:
        raise InsufficientDiskSpaceError(
            "Ruang disk tidak cukup untuk hasil ekstraksi.",
            detail=(
                f"Perkiraan kebutuhan: {human_bytes(needed_bytes)}; "
                f"ruang tersedia: {human_bytes(usage.free)}."
            ),
            advice="Kosongkan disk, pilih folder lain, atau kurangi jumlah frame.",
        )


class ProgressReporter:
    """Membatasi callback progres agar UI tidak kebanjiran sinyal (maks. 20/detik)."""

    def __init__(self, callback: ProgressCallback | None, total: int, min_interval: float = 0.05):
        self._callback = callback or (lambda done, total, ts: None)
        self.total = max(1, total)
        self.min_interval = min_interval
        self._last_emit = 0.0
        self._last_done = -1

    def __call__(self, done: int, ts: float, *, force: bool = False) -> None:
        now = time.monotonic()
        done = max(0, min(int(done), self.total))
        if done < self._last_done:
            done = self._last_done
        if not force:
            if done == self._last_done:
                return
            if now - self._last_emit < self.min_interval:
                return
        self._last_emit = now
        self._last_done = done
        self._callback(done, self.total, float(ts))


def is_complete_image(path: Path, fmt: str) -> bool:
    """Deteksi berkas gambar yang terpotong akibat proses dihentikan."""

    try:
        size = path.stat().st_size
        if size < 8:
            return False
        with path.open("rb") as handle:
            head = handle.read(8)
            handle.seek(max(0, size - 16))
            tail = handle.read()
    except OSError:
        return False

    if fmt == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in tail[-12:]
    return head.startswith(b"\xff\xd8") and tail.rstrip(b"\x00").endswith(b"\xff\xd9")


def finalize_temp_frames(
    temp_dir: Path,
    fmt: str,
    points: list[float],
    info: VideoInfo,
    opt: ExtractOptions,
    out_dir: Path,
) -> list[FrameResult]:
    """Pindahkan frame sementara ke nama final yang dapat diprediksi."""

    pattern = re.compile(rf"^frame_(\d+)\.{re.escape(fmt)}$")
    results: list[FrameResult] = []
    stem = sanitize_stem(info.path.stem)

    try:
        candidates = sorted(temp_dir.iterdir(), key=lambda p: p.name)
    except OSError:
        return results

    for candidate in candidates:
        match = pattern.match(candidate.name)
        if not match:
            continue
        zero_based = int(match.group(1)) - 1
        if not 0 <= zero_based < len(points):
            continue
        if not is_complete_image(candidate, fmt):
            log.warning("Melewati frame yang tidak lengkap: %s", candidate)
            continue

        timestamp = points[zero_based]
        filename = build_name(stem, zero_based + 1, timestamp, fmt, opt.template)
        destination = unique_path(out_dir, filename)
        try:
            os.replace(candidate, destination)
        except OSError:
            try:
                shutil.move(str(candidate), str(destination))
            except OSError as exc:
                raise OutputNotWritableError(
                    f"Hasil tidak dapat disimpan ke {destination.name}.",
                    detail=str(exc),
                    advice="Periksa izin folder dan ruang disk.",
                ) from exc

        results.append(
            FrameResult(
                path=destination,
                timestamp_s=timestamp,
                index=zero_based + 1,
                size_bytes=destination.stat().st_size,
            )
        )

    return sorted(results, key=lambda item: item.index)


def make_temp_dir(out_dir: Path) -> Path:
    """Buat folder kerja sementara dengan izin yang diwarisi dari folder keluaran.

    ``tempfile.mkdtemp`` memakai mode 0700. Di Windows mode itu diterjemahkan
    menjadi DACL khusus (OWNER RIGHTS + SYSTEM + Administrators), sehingga file
    yang dipindahkan keluar bisa tidak bisa dibuka oleh pengguna biasa ketika
    aplikasi berjalan elevated. ``Path.mkdir`` tanpa mode mempertahankan ACL
    warisan folder induk.
    """

    for _ in range(100):
        candidate = out_dir / f".frame-extractor-{secrets.token_hex(6)}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
        except OSError as exc:
            raise OutputNotWritableError(
                "Folder sementara untuk ekstraksi tidak dapat dibuat.",
                detail=str(exc),
                advice="Periksa izin folder keluaran dan ruang disk, lalu coba lagi.",
            ) from exc

    raise OutputNotWritableError(
        "Nama folder sementara tidak dapat dibuat.",
        advice="Coba lagi; jika tetap gagal, pilih folder keluaran lain.",
    )


def cleanup_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)


def safe_ts(points: list[float], index: int) -> float:
    if not points:
        return 0.0
    if not math.isfinite(points[min(index, len(points) - 1)]):
        return 0.0
    return points[min(index, len(points) - 1)]
