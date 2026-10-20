from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from tools.make_test_video import make_test_video  # noqa: E402

from frame_extractor.core.ffmpeg_tools import find_ffmpeg, find_ffprobe  # noqa: E402


@pytest.fixture(scope="session")
def test_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("media")
    return make_test_video(folder / "sample.mp4")


@pytest.fixture(scope="session")
def has_ffmpeg() -> bool:
    return find_ffmpeg() is not None


@pytest.fixture(scope="session")
def has_ffprobe() -> bool:
    return find_ffprobe() is not None


@pytest.fixture
def require_ffmpeg(has_ffmpeg: bool) -> None:
    """Lewati tes yang membutuhkan ffmpeg bila biner tidak tersedia."""

    if not has_ffmpeg:
        pytest.skip("ffmpeg tidak tersedia")
