from __future__ import annotations

from pathlib import Path

import pytest

from frame_extractor.core.errors import (
    MetadataError,
    UnsupportedVideoError,
    VideoNotFoundError,
)
from frame_extractor.core.probe import probe


@pytest.mark.integration
def test_probe_with_ffprobe(test_video: Path, has_ffprobe: bool) -> None:
    if not has_ffprobe:
        pytest.skip("ffprobe tidak tersedia")
    info = probe(test_video)
    assert info.duration_s == pytest.approx(10.0, abs=0.15)
    assert info.fps == pytest.approx(10.0, abs=0.1)
    assert (info.width, info.height) == (320, 240)
    assert 99 <= info.frame_count <= 101
    assert info.codec in ("mpeg4", "h264")
    assert info.path == test_video


@pytest.mark.integration
def test_probe_with_opencv_fallback(
    test_video: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    module = sys.modules["frame_extractor.core.probe"]
    monkeypatch.setattr(module, "find_ffprobe", lambda: None)
    info = probe(test_video)
    assert info.duration_s == pytest.approx(10.0, abs=0.2)
    assert info.fps == pytest.approx(10.0, abs=0.1)
    assert info.frame_count >= 99


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VideoNotFoundError):
        probe(tmp_path / "tidak-ada.mp4")


def test_wrong_extension(tmp_path: Path) -> None:
    path = tmp_path / "catatan.txt"
    path.write_text("bukan video")
    with pytest.raises(UnsupportedVideoError):
        probe(path)


def test_corrupt_video(tmp_path: Path) -> None:
    path = tmp_path / "rusak.mp4"
    path.write_bytes(b"ini bukan video sama sekali" * 50)
    with pytest.raises(MetadataError) as error:
        probe(path)
    assert "tidak terbaca" in error.value.message.lower() or "tidak" in error.value.message.lower()


def test_folder_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(VideoNotFoundError):
        probe(tmp_path / "folder.mp4")
