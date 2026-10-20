from __future__ import annotations

import time
from pathlib import Path

import pytest
from tools.make_test_video import SECOND_COLORS

from frame_extractor.core.errors import (
    EngineUnavailableError,
    InvalidOptionError,
    OutputNotWritableError,
)
from frame_extractor.core.extract import extract
from frame_extractor.core.extract_common import prepare_output_dir
from frame_extractor.core.extract_ffmpeg import extract_ffmpeg, jpeg_quality_to_qscale
from frame_extractor.core.extract_opencv import extract_opencv
from frame_extractor.core.models import ExtractOptions, VideoInfo
from frame_extractor.core.naming import build_name, sanitize_stem
from frame_extractor.core.probe import probe


def _info(path: Path) -> VideoInfo:
    return probe(path)


@pytest.mark.integration
def test_ffmpeg_extracts_ten_frames(
    test_video: Path, tmp_path: Path, require_ffmpeg: None
) -> None:
    info = _info(test_video)
    out = tmp_path / "hasil"
    results = extract_ffmpeg(info, ExtractOptions(mode="interval", interval_s=1.0, out_dir=out))
    assert len(results) == 10
    assert all(result.path.is_file() for result in results)
    assert [r.index for r in results] == list(range(1, 11))
    stem = sanitize_stem(test_video.stem)
    for result in results:
        expected = build_name(
            stem,
            result.index,
            result.timestamp_s,
            "png",
            ExtractOptions(mode="interval").template,
        )
        assert result.path.name == expected
        assert result.size_bytes == result.path.stat().st_size


@pytest.mark.integration
def test_pixel_content_matches_second(
    test_video: Path, tmp_path: Path, require_ffmpeg: None
) -> None:
    import cv2

    info = _info(test_video)
    results = extract_ffmpeg(
        info,
        ExtractOptions(mode="interval", interval_s=1.0, out_dir=tmp_path / "piksel"),
    )
    frame = cv2.imread(str(results[5].path))
    assert frame is not None
    # Kotak 5:30,5:30 pada video uji berisi warna murni detik tersebut.
    # Toleransi kecil diperlukan karena video uji memakai codec lossy (mp4v).
    expected = SECOND_COLORS[5]
    actual = tuple(int(v) for v in frame[10, 10])
    assert all(abs(a - b) <= 12 for a, b in zip(actual, expected, strict=True)), (
        actual,
        expected,
    )


@pytest.mark.integration
def test_opencv_and_ffmpeg_produce_same_names_and_count(
    test_video: Path, tmp_path: Path, require_ffmpeg: None
) -> None:
    info = _info(test_video)
    opts = ExtractOptions(mode="count", frame_total=7, out_dir=tmp_path / "a")
    ffmpeg_results = extract_ffmpeg(info, opts)
    opts_b = ExtractOptions(mode="count", frame_total=7, out_dir=tmp_path / "b")
    opencv_results = extract_opencv(info, opts_b)
    assert len(ffmpeg_results) == len(opencv_results) == 7
    assert [r.path.name for r in ffmpeg_results] == [r.path.name for r in opencv_results]
    assert [r.timestamp_s for r in ffmpeg_results] == [
        r.timestamp_s for r in opencv_results
    ]


@pytest.mark.integration
def test_count_mode_extracts_exact_count(
    test_video: Path, tmp_path: Path, require_ffmpeg: None
) -> None:
    info = _info(test_video)
    results = extract_ffmpeg(
        info,
        ExtractOptions(mode="count", frame_total=23, out_dir=tmp_path / "count"),
    )
    assert len(results) == 23


@pytest.mark.integration
def test_range_mode(test_video: Path, tmp_path: Path, require_ffmpeg: None) -> None:
    info = _info(test_video)
    results = extract_ffmpeg(
        info,
        ExtractOptions(
            mode="range",
            interval_s=2.0,
            start_s=2.0,
            end_s=8.0,
            out_dir=tmp_path / "range",
        ),
    )
    assert len(results) == 3
    assert [round(r.timestamp_s, 3) for r in results] == [2.0, 4.0, 6.0]


@pytest.mark.integration
def test_jpg_output(test_video: Path, tmp_path: Path, require_ffmpeg: None) -> None:
    info = _info(test_video)
    results = extract_ffmpeg(
        info,
        ExtractOptions(
            mode="count",
            frame_total=3,
            fmt="jpg",
            quality=70,
            out_dir=tmp_path / "jpg",
        ),
    )
    assert len(results) == 3
    assert all(result.path.suffix == ".jpg" for result in results)
    assert all(result.path.read_bytes()[:2] == b"\xff\xd8" for result in results)


@pytest.mark.integration
def test_auto_engine_uses_fallback_when_ffmpeg_missing(
    test_video: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    orchestrator = sys.modules["frame_extractor.core.extract"]
    monkeypatch.setattr(orchestrator, "find_ffmpeg", lambda: None)
    info = _info(test_video)
    results = extract(
        info,
        ExtractOptions(mode="count", frame_total=2, out_dir=tmp_path / "fallback"),
    )
    assert len(results) == 2


@pytest.mark.integration
def test_engine_opencv_missing_ffmpeg_is_fine(
    test_video: Path, tmp_path: Path
) -> None:
    info = _info(test_video)
    results = extract(
        info,
        ExtractOptions(mode="count", frame_total=2, out_dir=tmp_path / "ocv"),
        engine="opencv",
    )
    assert len(results) == 2


@pytest.mark.integration
def test_cancel_ffmpeg_keeps_partial_results(
    test_video: Path, tmp_path: Path, require_ffmpeg: None
) -> None:
    info = _info(test_video)
    cancelled = False
    started = time.monotonic()

    def should_cancel() -> bool:
        return cancelled

    def on_progress(done: int, total: int, ts: float) -> None:
        nonlocal cancelled
        if done >= 10:
            cancelled = True

    results = extract_ffmpeg(
        info,
        ExtractOptions(mode="interval", interval_s=0.0025, out_dir=tmp_path / "batal"),
        on_progress=on_progress,
        should_cancel=should_cancel,
    )
    elapsed = time.monotonic() - started
    assert elapsed < 3.0
    assert 0 < len(results) < 4000
    assert all(result.path.is_file() for result in results)


@pytest.mark.integration
def test_cancel_opencv_keeps_partial_results(test_video: Path, tmp_path: Path) -> None:
    info = _info(test_video)
    cancelled = False

    def on_progress(done: int, total: int, ts: float) -> None:
        nonlocal cancelled
        if done >= 3:
            cancelled = True

    results = extract_opencv(
        info,
        ExtractOptions(mode="interval", interval_s=0.02, out_dir=tmp_path / "batal2"),
        on_progress=on_progress,
        should_cancel=lambda: cancelled,
    )
    assert 0 < len(results) < 500
    assert all(result.path.is_file() for result in results)


def test_output_dir_defaults_next_to_video(test_video: Path) -> None:
    info = _info(test_video)
    out = prepare_output_dir(info, ExtractOptions(mode="interval"))
    assert out == test_video.parent.resolve()


def test_output_dir_cannot_be_created(tmp_path: Path, test_video: Path) -> None:
    info = _info(test_video)
    blocker = tmp_path / "berkas"
    blocker.write_text("x")
    with pytest.raises(OutputNotWritableError):
        prepare_output_dir(info, ExtractOptions(mode="interval", out_dir=blocker / "sub"))


def test_quality_mapping() -> None:
    assert jpeg_quality_to_qscale(100) == 2
    assert jpeg_quality_to_qscale(1) == 31
    assert 2 <= jpeg_quality_to_qscale(80) <= 31


def test_ffmpeg_missing_raises(monkeypatch: pytest.MonkeyPatch, test_video: Path) -> None:
    import frame_extractor.core.extract_ffmpeg as module

    monkeypatch.setattr(module, "find_ffmpeg", lambda: None)
    info = _info(test_video)
    with pytest.raises(EngineUnavailableError):
        extract_ffmpeg(info, ExtractOptions(mode="count", frame_total=1))


def test_invalid_options_still_raise() -> None:
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="interval", interval_s=-1)
