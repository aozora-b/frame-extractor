"""Palet, stylesheet, dan ikon aplikasi."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path
from string import Template

from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#14161a",
        "surface": "#1c1f24",
        "surface_alt": "#242830",
        "elevated": "#2b303a",
        "border": "#363c46",
        "text": "#f2f4f8",
        "muted": "#a8b0bd",
        "accent": "#5aa9ff",
        "accent_hover": "#7bbcff",
        "accent_text": "#08131f",
        "danger": "#ff8a80",
        "danger_bg": "#3a2020",
        "success": "#6ddc9b",
        "success_bg": "#18301f",
        "warning": "#f2c14e",
        "warning_bg": "#332b16",
        "focus": "#9ed1ff",
        "selection": "#2f5f8f",
        "progress_bg": "#2a3039",
    },
    "light": {
        "bg": "#f4f6f8",
        "surface": "#ffffff",
        "surface_alt": "#eef1f5",
        "elevated": "#ffffff",
        "border": "#d5dbe3",
        "text": "#16181c",
        "muted": "#5a6270",
        "accent": "#0b63b6",
        "accent_hover": "#0a56a0",
        "accent_text": "#ffffff",
        "danger": "#b42318",
        "danger_bg": "#fdecea",
        "success": "#176b3a",
        "success_bg": "#e7f5ec",
        "warning": "#7a5200",
        "warning_bg": "#fff4d6",
        "focus": "#0b63b6",
        "selection": "#cfe5ff",
        "progress_bg": "#e3e8ef",
    },
}


def _palette_tokens(name: str) -> dict[str, str]:
    return PALETTES["dark" if name == "dark" else "light"]


def stylesheet(theme: str) -> str:
    source = resources.files("frame_extractor.ui").joinpath("theme.qss").read_text("utf-8")
    return Template(source).substitute(_palette_tokens(theme))


def build_qpalette(theme: str):
    from PySide6.QtGui import QColor

    tokens = _palette_tokens(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens["surface_alt"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["surface"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["accent_text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens["elevated"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["muted"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(tokens["accent"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(tokens["muted"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(tokens["muted"])
    )
    return palette


def apply_theme(app: QApplication, theme: str) -> None:
    name = "dark" if theme == "dark" else "light"
    app.setProperty("themeName", name)
    app.setPalette(build_qpalette(name))
    app.setStyleSheet(stylesheet(name))


def app_icon() -> QIcon:
    candidates = [
        resources.files("frame_extractor").joinpath("assets").joinpath("icon.png"),
        Path(__file__).resolve().parents[3] / "assets" / "icon.png",
        Path(sys.executable).parent / "assets" / "icon.png",
    ]
    for candidate in candidates:
        try:
            path = Path(str(candidate))
        except TypeError:  # pragma: no cover - resource Traversable
            continue
        if path.is_file():
            return QIcon(str(path))
    return QIcon()
