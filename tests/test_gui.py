from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qt_app():
    """Satu QApplication untuk seluruh modul; Qt tidak suka instance dibuat ulang."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.mark.gui
@pytest.mark.integration
def test_gui_loads_extracts_and_shows_gallery(
    test_video: Path, tmp_path: Path, qt_app
) -> None:
    from tools.gui_smoke import run

    out = tmp_path / "hasil-gui"
    gallery_items, files = run(test_video, out)
    assert gallery_items == 10
    assert files == 10
    assert sorted(path.suffix for path in out.iterdir()) == [".png"] * 10


@pytest.mark.gui
def test_settings_panel_scrolls_when_height_is_limited(qt_app) -> None:
    from frame_extractor.ui.widgets.settings_panel import SettingsPanel

    panel = SettingsPanel()
    panel.resize(360, 400)
    panel.show()
    qt_app.processEvents()
    try:
        assert panel.scroll_area.verticalScrollBar().maximum() > 0
        assert panel.start_button.isVisible()
        assert panel.start_spin.minimumWidth() >= 120
    finally:
        panel.close()
        qt_app.processEvents()


@pytest.mark.gui
def test_settings_panel_stays_visible_in_small_window(qt_app, tmp_path: Path) -> None:
    from PySide6.QtCore import QPoint, QSettings

    from frame_extractor.ui.main_window import MainWindow

    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    window = MainWindow(settings=settings)
    window.resize(800, 500)
    window.show()
    qt_app.processEvents()
    try:
        panel = window.settings_panel
        panel_left = panel.mapTo(window, QPoint(0, 0)).x()
        assert panel_left >= 0
        assert panel_left + panel.width() <= window.width()
        assert panel.scroll_area.verticalScrollBar().maximum() > 0
        assert panel.start_button.isVisible()
    finally:
        window.close()
        qt_app.processEvents()
