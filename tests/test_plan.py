from __future__ import annotations

from pathlib import Path

import pytest

from frame_extractor.core.errors import InvalidOptionError, PlanError
from frame_extractor.core.models import ExtractOptions, VideoInfo
from frame_extractor.core.plan import estimate_output_bytes, plan_points


def make_info(duration: float = 60.0) -> VideoInfo:
    return VideoInfo(
        path=Path("video.mp4"),
        duration_s=duration,
        fps=30.0,
        width=1920,
        height=1080,
        frame_count=int(duration * 30),
        codec="h264",
    )


def test_interval_one_second_on_60_seconds() -> None:
    points = plan_points(make_info(60), ExtractOptions(mode="interval", interval_s=1.0))
    assert len(points) == 60
    assert points[0] == 0.0
    assert points[-1] == 59.0
    assert points == sorted(points)


def test_interval_three_seconds_on_ten_seconds() -> None:
    points = plan_points(make_info(10), ExtractOptions(mode="interval", interval_s=3.0))
    assert points == [0.0, 3.0, 6.0, 9.0]


def test_interval_respects_start_and_end() -> None:
    points = plan_points(
        make_info(60),
        ExtractOptions(mode="interval", interval_s=1.0, start_s=10.0, end_s=20.0),
    )
    assert len(points) == 10
    assert points[0] == 10.0
    assert points[-1] == 19.0


def test_interval_smaller_than_frame_rate() -> None:
    points = plan_points(make_info(10), ExtractOptions(mode="interval", interval_s=0.25))
    assert len(points) == 40
    assert points[-1] == pytest.approx(9.75)


def test_count_mode_evenly_spaced() -> None:
    points = plan_points(make_info(60), ExtractOptions(mode="count", frame_total=30))
    assert len(points) == 30
    gaps = [b - a for a, b in zip(points, points[1:], strict=False)]
    assert max(gaps) - min(gaps) < 1e-9
    assert points[0] == 0.0
    assert points[-1] < 60.0
    assert points[-1] == pytest.approx(58.0)


def test_count_mode_one_frame() -> None:
    points = plan_points(make_info(10), ExtractOptions(mode="count", frame_total=1))
    assert points == [0.0]


def test_count_mode_respects_range() -> None:
    points = plan_points(
        make_info(100),
        ExtractOptions(mode="count", frame_total=5, start_s=20, end_s=30),
    )
    assert len(points) == 5
    assert points[0] == 20.0
    assert points[-1] == pytest.approx(28.0)


def test_range_mode_honours_bounds() -> None:
    points = plan_points(
        make_info(60),
        ExtractOptions(mode="range", interval_s=2.0, start_s=10.0, end_s=20.0),
    )
    assert points == [10.0, 12.0, 14.0, 16.0, 18.0]


def test_range_mode_defaults_to_full_duration() -> None:
    points = plan_points(make_info(5), ExtractOptions(mode="range", interval_s=1.0))
    assert points == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_end_is_clamped_to_duration() -> None:
    points = plan_points(
        make_info(10),
        ExtractOptions(mode="range", interval_s=2.0, start_s=5.0, end_s=99.0),
    )
    assert points == [5.0, 7.0, 9.0]


def test_start_outside_duration_raises() -> None:
    with pytest.raises(PlanError):
        plan_points(make_info(10), ExtractOptions(mode="interval", start_s=20))


def test_zero_duration_raises() -> None:
    with pytest.raises(PlanError):
        plan_points(make_info(0), ExtractOptions(mode="interval"))


def test_too_many_frames_raises() -> None:
    with pytest.raises(PlanError):
        plan_points(make_info(10_000), ExtractOptions(mode="count", frame_total=250_000))


def test_options_validation() -> None:
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="interval", interval_s=0)
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="count", frame_total=0)
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="interval", quality=0)
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="interval", start_s=5, end_s=5)
    with pytest.raises(InvalidOptionError):
        ExtractOptions(mode="interval", fmt="gif")  # type: ignore[arg-type]


def test_estimate_output_bytes_png_larger_than_jpg() -> None:
    info = make_info(10)
    png = extract_estimate = estimate_output_bytes(info, ExtractOptions(mode="count"), 10)
    jpg = estimate_output_bytes(
        info, ExtractOptions(mode="count", fmt="jpg", quality=80), 10
    )
    assert extract_estimate == png
    assert png > jpg > 0
