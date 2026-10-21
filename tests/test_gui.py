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
def test_output_clear_button_fits_inside_line_edit(qt_app) -> None:
    from PySide6.QtWidgets import QToolButton

    from frame_extractor.ui.theme import apply_theme
    from frame_extractor.ui.widgets.settings_panel import SettingsPanel

    apply_theme(qt_app, "dark")
    panel = SettingsPanel()
    panel.resize(360, 700)
    panel.show()
    panel.out_edit.setText("E:/ujicoba")
    qt_app.processEvents()
    try:
        buttons = panel.out_edit.findChildren(QToolButton)
        assert len(buttons) == 1
        clear_button = buttons[0]
        assert clear_button.isVisible() is True
        assert panel.out_edit.rect().contains(clear_button.geometry())
        assert clear_button.width() <= 24
        assert clear_button.height() <= 24
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


@pytest.mark.gui
def test_language_switch_updates_interface_and_persists(qt_app, tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    from frame_extractor.core.formats import FILE_DIALOG_FILTER
    from frame_extractor.ui.i18n import language, set_language, tr
    from frame_extractor.ui.main_window import MainWindow

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    set_language("id")
    first = MainWindow(settings=settings)
    try:
        assert language() == "id"
        assert first.file_menu.title() == "Berkas"
        assert first.view_menu.title() == "Tampilan"
        assert first.language_menu.title() == "Bahasa"
        assert first.language_actions["id"].isChecked() is True
        assert first.language_actions["en"].isChecked() is False
        assert first.drop_zone.title_label.text() == "Jatuhkan video atau folder di sini"
        assert first.drop_zone.choose_button.text() == "Pilih video"
        assert first.settings_panel.start_button.text() == "Mulai ekstraksi"
        assert first.settings_panel.mode_combo.itemText(0) == "Satu frame tiap N detik"
        assert first.queue_panel.title_label.text() == "Antrean"
        assert first.queue_panel.count_label.text() == "0 video"
        assert first.gallery.title_label.text() == "Hasil"
        assert first.gallery.summary_label.text() == "Belum ada hasil"
        assert first.status_label.text().startswith("Siap")
        assert tr(FILE_DIALOG_FILTER).startswith("Berkas video")

        first.language_actions["en"].trigger()
        qt_app.processEvents()

        assert language() == "en"
        assert settings.value("language") == "en"
        assert first.file_menu.title() == "File"
        assert first.view_menu.title() == "View"
        assert first.language_menu.title() == "Language"
        assert first.language_actions["en"].isChecked() is True
        assert first.language_actions["id"].isChecked() is False
        assert first.drop_zone.title_label.text() == "Drop a video or folder here"
        assert first.drop_zone.choose_button.text() == "Choose video"
        assert first.settings_panel.start_button.text() == "Start extraction"
        assert first.settings_panel.mode_combo.itemText(0) == "One frame every N seconds"
        assert first.settings_panel.interval_spin.suffix().strip() == "s"
        assert first.queue_panel.title_label.text() == "Queue"
        assert first.queue_panel.count_label.text() == "0 videos"
        assert first.gallery.title_label.text() == "Results"
        assert first.gallery.summary_label.text() == "No results yet"
        assert first.status_label.text().startswith("Ready")
        assert tr(FILE_DIALOG_FILTER).startswith("Video files")
        assert tr(FILE_DIALOG_FILTER).endswith("All files (*)")
    finally:
        first.close()
        qt_app.processEvents()

    second = MainWindow(settings=settings)
    try:
        assert language() == "en"
        assert second.file_menu.title() == "File"
        assert second.language_actions["en"].isChecked() is True
        assert second.settings_panel.start_button.text() == "Start extraction"

        second.language_actions["id"].trigger()
        qt_app.processEvents()
        assert language() == "id"
        assert settings.value("language") == "id"
        assert second.file_menu.title() == "Berkas"
        assert second.settings_panel.start_button.text() == "Mulai ekstraksi"
    finally:
        second.close()
        set_language("id")
        qt_app.processEvents()


@pytest.mark.gui
def test_language_switch_rerenders_queue_gallery_and_status(qt_app, tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    from frame_extractor.core.models import FrameResult, VideoInfo
    from frame_extractor.ui.i18n import language, set_language
    from frame_extractor.ui.main_window import MainWindow
    from frame_extractor.ui.models import QueueModel

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    set_language("id")
    window = MainWindow(settings=settings)
    path = tmp_path / "video.mp4"
    info = VideoInfo(path, 65.0, 29.97, 320, 240, 1234, "h264")
    frames = [
        FrameResult(path, 1.0, 1, 1024),
        FrameResult(path, 2.0, 2, 512),
    ]
    try:
        model = window.queue_panel.model
        model.add_paths([path])
        model.update_entry(path, info=info, state="ready", detail="", detail_kind="media")
        index = model.index(model.row_for_path(path), 0)
        assert model.data(index, QueueModel.DetailRole) == "1 mnt 05 dtk · 320×240"

        window.info_card.set_info(info)
        assert window.info_card.duration.value.text() == "1 mnt 05 dtk"
        assert window.info_card.frames.value.text() == "1.234"

        model.update_entry(path, state="done", detail="", detail_kind="done", results=frames)
        assert model.data(index, QueueModel.DetailRole) == "2 gambar · 1,5 KB"

        window.gallery.set_results(frames, elapsed_s=65.0, expected_total=2)
        assert window.gallery.summary_label.text() == "2 gambar · 1,5 KB · 1 mnt 05 dtk"

        window._set_footer("Selesai · {n} gambar · {size}", n=2, size_bytes=1536)
        window._set_eta(seconds=65)
        window._set_count_total(1234)
        assert window.status_label.text() == "Selesai · 2 gambar · 1,5 KB"
        assert window.eta_label.text() == "sisa 1 mnt 05 dtk"
        assert window.count_label.text() == "1.234"
        window._set_count_progress(1234, 2000)
        assert window.count_label.text() == "1.234/2.000"

        window.language_actions["en"].trigger()
        qt_app.processEvents()

        assert language() == "en"
        assert model.data(index, QueueModel.DetailRole) == "2 frames · 1.5 KB"
        assert window.info_card.duration.value.text() == "1 min 05 s"
        assert window.info_card.frames.value.text() == "1,234"
        assert window.gallery.summary_label.text() == "2 frames · 1.5 KB · 1 min 05 s"
        assert window.status_label.text() == "Done · 2 frames · 1.5 KB"
        assert window.eta_label.text() == "remaining 1 min 05 s"
        assert window.count_label.text() == "1,234/2,000"

        window.language_actions["id"].trigger()
        qt_app.processEvents()
        assert model.data(index, QueueModel.DetailRole) == "2 gambar · 1,5 KB"
        assert window.gallery.summary_label.text() == "2 gambar · 1,5 KB · 1 mnt 05 dtk"
        assert window.count_label.text() == "1.234/2.000"
    finally:
        window.close()
        set_language("id")
        qt_app.processEvents()


@pytest.mark.gui
def test_settings_panel_rerenders_estimate_note_and_error(qt_app) -> None:
    from frame_extractor.ui.i18n import set_language
    from frame_extractor.ui.widgets.settings_panel import SettingsPanel

    set_language("id")
    panel = SettingsPanel()
    try:
        panel.set_estimate(1234, 1536, 65)
        panel.set_note(
            "Video ini lebih dari 2 jam. Perkiraan waktu ekstraksi ± {duration}; "
            "proses berjalan di latar belakang.",
            duration_s=65,
        )
        panel.set_error("Berkas tidak ditemukan: video.mp4")
        assert panel.estimate_number.text() == "1.234 gambar"
        assert panel.estimate_detail.text() == "± 1,5 KB · ± 1 mnt 05 dtk"
        assert "1 mnt 05 dtk" in panel.note_label.text()
        assert panel.error_label.text() == "Berkas tidak ditemukan: video.mp4"

        set_language("en")
        panel.retranslate()
        assert panel.mode_combo.itemText(0) == "One frame every N seconds"
        assert panel.interval_spin.suffix().strip() == "s"
        assert panel.start_button.text() == "Start extraction"
        assert panel.estimate_number.text() == "1,234 frames"
        assert panel.estimate_detail.text() == "± 1.5 KB · ± 1 min 05 s"
        assert "1 min 05 s" in panel.note_label.text()
        assert panel.error_label.text() == "File not found: video.mp4"

        set_language("id")
        panel.retranslate()
        assert panel.estimate_number.text() == "1.234 gambar"
        assert panel.estimate_detail.text() == "± 1,5 KB · ± 1 mnt 05 dtk"
        assert panel.error_label.text() == "Berkas tidak ditemukan: video.mp4"
    finally:
        panel.close()
        set_language("id")
        qt_app.processEvents()


@pytest.mark.gui
def test_error_dialog_and_core_messages_are_translated(qt_app) -> None:
    from frame_extractor.ui.i18n import set_language, translate_message
    from frame_extractor.ui.widgets.error_dialog import ErrorDialog

    set_language("en")
    dialog = ErrorDialog(
        "Berkas tidak ditemukan",
        "Berkas tidak ditemukan: video.mp4",
        "Periksa apakah berkas dipindahkan atau namanya berubah.",
        "FileNotFoundError: video.mp4",
    )
    try:
        assert dialog.heading.text() == "File not found"
        assert dialog.body.text() == "File not found: video.mp4"
        assert (
            dialog.advice_label.text()
            == "Advice: Check whether the file was moved or renamed."
        )
        assert dialog.copy_button.text() == "Copy details"
        assert dialog.close_button.text() == "Close"
        assert dialog.detail_toggle.text() == "Show technical details"
        dialog.detail_toggle.setChecked(True)
        assert dialog.detail_toggle.text() == "Hide technical details"
        assert translate_message("Folder keluaran tidak dapat dibuat: E:\\hasil") == (
            "Could not create the output folder: E:\\hasil"
        )
        assert translate_message("Durasi video ini 10.0 detik; turunkan waktu mulai.") == (
            "This video is 10.0 seconds long; lower the start time."
        )
    finally:
        dialog.close()
        set_language("id")
        qt_app.processEvents()

    assert translate_message("Berkas tidak ditemukan: video.mp4") == (
        "Berkas tidak ditemukan: video.mp4"
    )


def test_humanize_english_formats_keep_indonesian_defaults() -> None:
    from frame_extractor.core.humanize import eta_text, human_bytes, human_duration

    assert human_bytes(1536) == "1,5 KB"
    assert human_bytes(1536, "en") == "1.5 KB"
    assert human_duration(65) == "1 mnt 05 dtk"
    assert human_duration(65, "en") == "1 min 05 s"
    assert eta_text(65) == "sisa 1 mnt 05 dtk"
    assert eta_text(65, "en") == "remaining 1 min 05 s"
    assert eta_text(None, "en") == "calculating remaining time…"
