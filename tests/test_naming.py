from __future__ import annotations

from pathlib import Path

import pytest

from frame_extractor.core.errors import InvalidOptionError, OutputNotWritableError
from frame_extractor.core.naming import (
    build_name,
    format_time,
    sanitize_filename,
    sanitize_stem,
    unique_path,
    validate_template,
)

DEFAULT = "{stem}_{index:06d}_{time}.{ext}"


@pytest.mark.parametrize(
    ("raw", "forbidden"),
    [
        ('liburan:2024*"<>|?', ': * " < > | ?'),
        ("folder/bagian\\video", "/ \\"),
        ("nama\x00dengan\x1fkontrol", "\x00\x1f"),
    ],
)
def test_sanitize_removes_windows_forbidden_characters(raw: str, forbidden: str) -> None:
    result = sanitize_stem(raw)
    for char in forbidden.split():
        assert char not in result


def test_sanitize_strips_trailing_dots_and_spaces() -> None:
    assert sanitize_stem("video...   ") == "video"
    assert sanitize_stem("   ") == "video"
    assert sanitize_stem("  nama  ") == "nama"


@pytest.mark.parametrize("reserved", ["CON", "con", "PRN", "NUL", "COM1", "lpt9"])
def test_sanitize_reserved_windows_names(reserved: str) -> None:
    assert sanitize_stem(reserved).upper().startswith("_")


def test_sanitize_keeps_unicode() -> None:
    assert sanitize_stem("Liburan di Bali — 2024") == "Liburan di Bali — 2024"


def test_sanitize_filename_blocks_path_separators() -> None:
    result = sanitize_filename("../../etc/passwd.png")
    assert "/" not in result
    assert "\\" not in result


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00-00-00"), (3, "00-00-03"), (123, "00-02-03"), (3661, "01-01-01"), (-5, "00-00-00")],
)
def test_format_time(seconds: float, expected: str) -> None:
    assert format_time(seconds) == expected


def test_build_name_default_pattern() -> None:
    assert build_name("liburan", 123, 123, "png", DEFAULT) == "liburan_000123_00-02-03.png"


def test_build_name_starts_at_one_and_pads_six_digits() -> None:
    assert build_name("a", 1, 0, "jpg", DEFAULT) == "a_000001_00-00-00.jpg"


def test_build_name_sanitizes_stem() -> None:
    result = build_name("a:b*c", 1, 0, "png", DEFAULT)
    assert result == "a_b_c_000001_00-00-00.png"


def test_build_name_requires_extension_placeholder() -> None:
    with pytest.raises(InvalidOptionError):
        build_name("a", 1, 0, "png", "{stem}_{index:06d}")


def test_build_name_rejects_unknown_extension() -> None:
    with pytest.raises(InvalidOptionError):
        build_name("a", 1, 0, "gif", DEFAULT)


@pytest.mark.parametrize(
    "template",
    [
        "",
        "   ",
        "{stem}_{index:06d}_{unknown}.{ext}",
        "{stem}_{time}.{ext}",
        "{stem}_{index:06d}",
        "{stem}_{index:06d_{time}.{ext}",
    ],
)
def test_validate_template_rejects_bad_patterns(template: str) -> None:
    with pytest.raises(InvalidOptionError):
        validate_template(template)


def test_build_name_does_not_allow_traversal() -> None:
    result = build_name("a", 1, 0, "png", "../{stem}_{index:06d}.{ext}")
    assert ".." not in result or "/" not in result
    assert "/" not in result and "\\" not in result


def test_unique_path_adds_suffix(tmp_path: Path) -> None:
    target = tmp_path / "frame.png"
    assert unique_path(tmp_path, "frame.png") == target
    target.write_bytes(b"x")
    first = unique_path(tmp_path, "frame.png")
    assert first.name == "frame-1.png"
    first.write_bytes(b"x")
    assert unique_path(tmp_path, "frame.png").name == "frame-2.png"


def test_unique_path_never_overwrites(tmp_path: Path) -> None:
    existing = tmp_path / "hasil_000001_00-00-00.png"
    existing.write_bytes(b"lama")
    selected = unique_path(tmp_path, existing.name)
    selected.write_bytes(b"baru")
    assert existing.read_bytes() == b"lama"
    assert selected.read_bytes() == b"baru"


def test_long_names_are_truncated() -> None:
    name = build_name("x" * 400, 1, 0, "png", DEFAULT)
    assert len(name) <= 180
    assert name.endswith(".png")


def test_unique_path_exhaustion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: True)
    with pytest.raises(OutputNotWritableError):
        unique_path(tmp_path, "a.png")
