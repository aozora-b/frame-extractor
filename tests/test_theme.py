from __future__ import annotations

import pytest

from frame_extractor.ui.theme import PALETTES


def _luminance(hex_color: str) -> float:
    values = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in values
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("text", "bg"),
        ("text", "surface"),
        ("text", "surface_alt"),
        ("muted", "bg"),
        ("muted", "surface"),
        ("accent_text", "accent"),
        ("danger", "danger_bg"),
        ("warning", "warning_bg"),
        ("success", "success_bg"),
    ],
)
def test_text_contrast_meets_wcag_aa(theme: str, foreground: str, background: str) -> None:
    palette = PALETTES[theme]
    assert _contrast(palette[foreground], palette[background]) >= 4.5
