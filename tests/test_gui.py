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


def _video_info(path: Path):
    from frame_extractor.core.models import VideoInfo

    return VideoInfo(path, 10.0, 30.0, 320, 240, 300, "h264")


def _make_window(qt_app, tmp_path: Path):
    from PySide6.QtCore import QSettings

    from frame_extractor.ui.main_window import MainWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    return window


@pytest.mark.gui
def test_queue_retries_failed_but_keeps_done_entries(qt_app, tmp_path: Path) -> None:
    from frame_extractor.ui.models import QueueModel

    model = QueueModel()
    paths = [tmp_path / name for name in ("a.mp4", "b.mp4", "c.mp4")]
    model.add_paths(paths)
    model.update_entry(paths[0], state="done", detail="10 gambar")
    model.update_entry(paths[1], state="error", detail="gagal")
    model.update_entry(paths[2], state="cancelled", detail="dibatalkan")

    assert model.prepare_run() is True
    assert [entry.state for entry in model.entries()] == [
        "done",
        "waiting",
        "waiting",
    ]
    assert model.has_pending() is True

    for path in paths:
        model.update_entry(path, state="done")
    assert model.has_pending() is False
    assert model.prepare_run() is False


@pytest.mark.gui
def test_start_batch_skips_completed_entries(qt_app, tmp_path: Path) -> None:
    window = _make_window(qt_app, tmp_path)
    model = window.queue_panel.model
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    model.add_paths([first, second])
    model.update_entry(first, info=_video_info(first), state="done", detail="10 gambar")
    model.update_entry(second, info=_video_info(second), state="ready")
    launched: list[Path] = []
    window._launch_extraction = lambda path, info: launched.append(path)  # type: ignore[method-assign]
    try:
        window._start_batch()
        assert launched == [second]
        assert model.entry(0).state == "done"
        assert model.entry(1).state == "ready"

        window._finish_batch()
        model.update_entry(second, state="done", detail="10 gambar")
        launched.clear()
        window._start_batch()
        assert launched == []
        assert window._running is False
        assert "sudah selesai" in window.status_label.text()
    finally:
        window._running = False
        window.close()
        qt_app.processEvents()


@pytest.mark.gui
def test_queue_panel_remove_button_emits_selected_path(qt_app, tmp_path: Path) -> None:
    from frame_extractor.ui.widgets.queue_panel import QueuePanel

    panel = QueuePanel()
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    panel.model.add_paths([first, second])
    panel.select_path(first)
    emitted: list[Path] = []
    panel.removeRequested.connect(emitted.append)
    try:
        assert panel.remove_button.isEnabled() is True
        panel.remove_button.click()
        assert emitted == [first]
        assert panel.model.rowCount() == 2
    finally:
        panel.close()
        qt_app.processEvents()


@pytest.mark.gui
def test_remove_selected_entry_updates_current_and_empty_state(
    qt_app, tmp_path: Path
) -> None:
    window = _make_window(qt_app, tmp_path)
    model = window.queue_panel.model
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    model.add_paths([first, second])
    model.update_entry(first, info=_video_info(first), state="done", detail="10 gambar")
    model.update_entry(second, info=_video_info(second), state="ready")
    window.queue_panel.select_path(first)
    try:
        assert window._current_path == first
        assert window.queue_panel.remove_button.isEnabled() is True

        window._remove_path(first)
        assert model.rowCount() == 1
        assert model.entry(0).path == second
        assert window._current_path == second
        assert window.stack.currentWidget() is window.loaded_page
        assert window.settings_panel.start_button.isEnabled() is True

        window._remove_path(second)
        assert model.rowCount() == 0
        assert window._current_path is None
        assert window.stack.currentWidget() is window.empty_page
        assert window.settings_panel.start_button.isEnabled() is False
        assert window.queue_panel.remove_button.isEnabled() is False
    finally:
        window.close()
        qt_app.processEvents()
