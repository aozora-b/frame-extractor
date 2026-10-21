"""Jendela utama dan orkestrasi antrean, thread, serta keadaan UI."""

from __future__ import annotations

import contextlib
import logging
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QSettings, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core.errors import DomainError
from ..core.formats import FILE_DIALOG_FILTER, is_video_file, scan_folder
from ..core.humanize import eta_text, human_bytes, human_duration
from ..core.models import ExtractOptions, FrameResult, VideoInfo
from ..core.plan import estimate_output_bytes, plan_points
from ..logging_setup import get_log_path
from ..worker import ExtractWorker, ProbeWorker
from .i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    format_count,
    language,
    normalize_language,
    set_language,
    tr,
    translator,
)
from .theme import app_icon, apply_theme
from .widgets.drop_zone import DropZone
from .widgets.error_dialog import show_error
from .widgets.queue_panel import QueuePanel
from .widgets.results_gallery import ResultsGallery
from .widgets.settings_panel import SettingsPanel
from .widgets.video_info import VideoInfoCard

log = logging.getLogger(__name__)


class _LogBridge(QObject):
    message = Signal(str)


class _QtLogHandler(logging.Handler):
    def __init__(self, bridge: _LogBridge) -> None:
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            self.bridge.message.emit(self.format(record))


def _split_detail(detail: str) -> tuple[str, str, str]:
    """Pisahkan pesan, saran, dan detail teknis dari teks worker."""

    technical = ""
    marker = "\n\nDetail teknis:\n"
    if marker in detail:
        detail, technical = detail.split(marker, 1)
    advice = ""
    marker = "\n\nSaran: "
    if marker in detail:
        detail, advice = detail.split(marker, 1)
    return detail.strip(), advice.strip(), technical.strip()


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings()
        set_language(normalize_language(self.settings.value("language", DEFAULT_LANGUAGE)))
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(800, 500)
        self.resize(1180, 780)
        self.setAcceptDrops(True)

        self._theme = "dark"
        self._current_path: Path | None = None
        self._current_info: VideoInfo | None = None
        self._running = False
        self._closing = False
        self._cancel_requested = False
        self._batch_options: ExtractOptions | None = None
        self._batch_results: list[FrameResult] = []
        self._batch_errors: list[tuple[str, str, str]] = []
        self._batch_started = 0.0
        self._error_shown = False
        self._current_total = 0
        self._current_done = 0
        self._item_started = 0.0
        self._eta_ema: float | None = None
        self._last_dir = str(Path.home())
        self._footer_source = ""
        self._footer_kwargs: dict[str, object] = {}
        self._eta_source = ""
        self._eta_seconds: float | None = None
        self._count_total = 0
        self._count_current = 0
        self._count_total_only = False
        self._count_show_zero = False

        self._extract_thread: QThread | None = None
        self._extract_worker: ExtractWorker | None = None
        self._probe_thread: QThread | None = None
        self._probe_worker: ProbeWorker | None = None
        self._probe_queue: deque[Path] = deque()
        self._probe_active_path: Path | None = None
        self._probe_active_ok = False
        self._batch_pending_path: Path | None = None

        self._build_ui()
        self._build_menu()
        self._build_log_dock()
        self._restore_settings()
        apply_theme(QApplication.instance(), self._theme)
        self._sync_theme_ui()
        self._install_log_handler()
        self._recalc_estimate()
        self._show_page(self.empty_page)
        self._set_footer("Siap — pilih video untuk memulai")
        self._update_actions()
        self._set_tab_order()
        translator.languageChanged.connect(self._on_language_changed)
        self.retranslate()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(18)

        self.stack = QStackedWidget()
        self.drop_zone = DropZone()
        self.drop_zone.browseFiles.connect(self._choose_files)
        self.drop_zone.browseFolder.connect(self._choose_folder)
        self.drop_zone.pathsDropped.connect(self._paths_dropped)

        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.addWidget(self.drop_zone)

        self.loaded_page = QWidget()
        loaded_layout = QVBoxLayout(self.loaded_page)
        loaded_layout.setContentsMargins(0, 0, 0, 0)
        loaded_layout.setSpacing(12)
        self.info_card = VideoInfoCard()
        loaded_layout.addWidget(self.info_card)
        self.queue_panel = QueuePanel()
        self.queue_panel.addRequested.connect(self._choose_files)
        self.queue_panel.removeRequested.connect(self._remove_path)
        self.queue_panel.currentPathChanged.connect(self._on_queue_current)
        loaded_layout.addWidget(self.queue_panel, 1)

        self.gallery = ResultsGallery()
        self.gallery.openFolderRequested.connect(self._open_results_folder)

        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.loaded_page)
        self.stack.addWidget(self.gallery)

        self.settings_panel = SettingsPanel()
        self.settings_panel.settingsChanged.connect(self._on_settings_changed)
        self.settings_panel.startRequested.connect(self._start_batch)

        body_layout.addWidget(self.stack, 1)
        body_layout.addWidget(self.settings_panel, 0)
        outer.addWidget(body, 1)
        outer.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(self.windowIcon().pixmap(36, 36))
        icon_label.setFixedSize(36, 36)
        layout.addWidget(icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("BrandTitle")
        text_box.addWidget(title)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("Muted")
        text_box.addWidget(self.subtitle)
        layout.addLayout(text_box)
        layout.addStretch(1)

        self.theme_button = QToolButton()
        self.theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_button)

        self.info_button = QToolButton()
        self.info_button.clicked.connect(self._show_about)
        layout.addWidget(self.info_button)
        return header

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setMinimumHeight(58)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(14)

        self.status_label = QLabel()
        self.status_label.setMinimumWidth(220)
        self.status_label.setWordWrap(False)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("Muted")
        self.count_label.setMinimumWidth(72)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.count_label)

        self.eta_label = QLabel("")
        self.eta_label.setObjectName("Muted")
        self.eta_label.setMinimumWidth(150)
        layout.addWidget(self.eta_label)

        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("Danger")
        self.cancel_button.clicked.connect(self._request_cancel)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        return footer

    def _build_menu(self) -> None:
        bar = self.menuBar()

        self.file_menu = bar.addMenu("")
        self.open_action = QAction("", self)
        self.open_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.open_action.triggered.connect(self._choose_files)
        self.file_menu.addAction(self.open_action)

        self.add_action = QAction("", self)
        self.add_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.add_action.triggered.connect(self._choose_files)
        self.file_menu.addAction(self.add_action)

        self.file_menu.addSeparator()
        self.quit_action = QAction("", self)
        self.quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.quit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.quit_action)

        self.extract_menu = bar.addMenu("")
        self.start_action = QAction("", self)
        self.start_action.setShortcuts(
            [QKeySequence("Ctrl+Return"), QKeySequence("Ctrl+Enter")]
        )
        self.start_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.start_action.triggered.connect(self._start_batch)
        self.extract_menu.addAction(self.start_action)

        self.cancel_action = QAction("", self)
        self.cancel_action.setShortcut(QKeySequence("Esc"))
        self.cancel_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.cancel_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserStop)
        )
        self.cancel_action.triggered.connect(self._request_cancel)
        self.extract_menu.addAction(self.cancel_action)

        self.extract_menu.addSeparator()
        self.open_folder_action = QAction("", self)
        self.open_folder_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.open_folder_action.triggered.connect(self._open_results_folder)
        self.extract_menu.addAction(self.open_folder_action)

        self.view_menu = bar.addMenu("")
        self.dark_action = QAction("", self)
        self.dark_action.setCheckable(True)
        self.dark_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.dark_action.triggered.connect(self._set_dark_from_action)
        self.view_menu.addAction(self.dark_action)

        self.log_action = QAction("", self)
        self.log_action.setCheckable(True)
        self.log_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.log_action.toggled.connect(self._toggle_log)
        self.view_menu.addAction(self.log_action)

        self.language_menu = self.view_menu.addMenu("")
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.language_actions: dict[str, QAction] = {}
        for code, name in LANGUAGES:
            action = QAction(tr(name), self)
            action.setCheckable(True)
            action.setData(code)
            action.triggered.connect(
                lambda _checked=False, selected=code: self._set_language(selected)
            )
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        self.help_menu = bar.addMenu("")
        self.shortcuts_action = QAction("", self)
        self.shortcuts_action.triggered.connect(self._show_shortcuts)
        self.help_menu.addAction(self.shortcuts_action)
        self.about_action = QAction("", self)
        self.about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(self.about_action)
        self._sync_language_actions()

    def _set_language(self, code: str) -> None:
        selected = normalize_language(code)
        if selected == language():
            self._sync_language_actions()
            return
        set_language(selected)

    def _on_language_changed(self, selected: str) -> None:
        self.settings.setValue("language", normalize_language(selected))
        self.retranslate()

    def _sync_language_actions(self) -> None:
        for code, action in getattr(self, "language_actions", {}).items():
            action.setChecked(code == language())

    def retranslate(self) -> None:
        self.subtitle.setText(tr("Ambil gambar diam dari video"))
        self.theme_button.setText(tr("Tema"))
        self.theme_button.setToolTip(tr("Ganti tema terang/gelap"))
        self.theme_button.setAccessibleName(tr("Ganti tema"))
        self.info_button.setText(tr("Info"))
        self.info_button.setToolTip(tr("Tentang aplikasi dan pintasan keyboard"))
        self.info_button.setAccessibleName(tr("Tentang aplikasi"))
        self.progress_bar.setAccessibleName(tr("Progres ekstraksi"))
        self.cancel_button.setText(tr("Batal"))
        self.cancel_button.setToolTip(
            tr("Hentikan proses (Esc); hasil yang sudah tersimpan tetap ada")
        )
        self.cancel_button.setAccessibleName(tr("Batalkan ekstraksi"))

        self.file_menu.setTitle(tr("Berkas"))
        self.open_action.setText(tr("Buka video…"))
        self.add_action.setText(tr("Tambah ke antrean…"))
        self.quit_action.setText(tr("Keluar"))
        self.extract_menu.setTitle(tr("Ekstraksi"))
        self.start_action.setText(tr("Mulai ekstraksi"))
        self.cancel_action.setText(tr("Batalkan"))
        self.open_folder_action.setText(tr("Buka folder hasil"))
        self.view_menu.setTitle(tr("Tampilan"))
        self.dark_action.setText(tr("Tema gelap"))
        self.log_action.setText(tr("Panel log"))
        self.language_menu.setTitle(tr("Bahasa"))
        self.language_actions["id"].setText(tr("Bahasa Indonesia"))
        self.language_actions["en"].setText(tr("English"))
        self.help_menu.setTitle(tr("Bantuan"))
        self.shortcuts_action.setText(tr("Pintasan keyboard"))
        self.about_action.setText(tr("Tentang Frame Extractor"))
        self.log_dock.setWindowTitle(tr("Log"))
        self.log_edit.setAccessibleName(tr("Log aplikasi"))

        self.drop_zone.retranslate()
        self.info_card.retranslate()
        self.queue_panel.retranslate()
        self.settings_panel.retranslate()
        self.gallery.retranslate()
        self._sync_language_actions()
        self._sync_theme_ui()
        self._render_footer()
        self._render_eta()
        self._render_count()
        if not self._running:
            self._recalc_estimate()
        self._update_actions()

    def _build_log_dock(self) -> None:
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("LogDock")
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(3000)
        self.log_edit.setAccessibleName("Log aplikasi")
        self.log_dock.setWidget(self.log_edit)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

    def _set_tab_order(self) -> None:
        widgets = [
            self.drop_zone.choose_button,
            self.drop_zone.folder_button,
            self.queue_panel.add_button,
            self.queue_panel.remove_button,
            self.queue_panel.view,
            self.settings_panel.mode_combo,
            self.settings_panel.interval_spin,
            self.settings_panel.count_spin,
            self.settings_panel.start_spin,
            self.settings_panel.end_spin,
            self.settings_panel.format_combo,
            self.settings_panel.quality_slider,
            self.settings_panel.quality_spin,
            self.settings_panel.out_edit,
            self.settings_panel.browse_button,
            self.settings_panel.start_button,
            self.cancel_button,
        ]
        for first, second in zip(widgets, widgets[1:], strict=False):
            QWidget.setTabOrder(first, second)

    # ------------------------------------------------------------- log & tema
    def _install_log_handler(self) -> None:
        self._log_bridge = _LogBridge(self)
        self._log_bridge.message.connect(self._append_log)
        handler = _QtLogHandler(self._log_bridge)
        handler.setFormatter(logging.Formatter("%H:%M:%S  %(levelname)-7s  %(message)s"))
        logging.getLogger().addHandler(handler)
        self._log_handler = handler

    def _append_log(self, message: str) -> None:
        self.log_edit.appendPlainText(message)

    def _toggle_log(self, checked: bool) -> None:
        self.log_dock.setVisible(checked)

    def _toggle_theme(self) -> None:
        self._apply_theme("light" if self._theme == "dark" else "dark")

    def _set_dark_from_action(self, checked: bool) -> None:
        self._apply_theme("dark" if checked else "light")

    def _apply_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        apply_theme(QApplication.instance(), self._theme)
        self.queue_panel.view.viewport().update()
        self._sync_theme_ui()
        self.settings.setValue("theme", self._theme)

    def _sync_theme_ui(self) -> None:
        self.dark_action.setChecked(self._theme == "dark")
        target = tr("terang") if self._theme == "dark" else tr("gelap")
        self.theme_button.setToolTip(
            tr(
                "Tema saat ini: {theme}. Klik untuk beralih ke {target}.",
                theme=tr("gelap") if self._theme == "dark" else tr("terang"),
                target=target,
            )
        )

    # ------------------------------------------------------------- file input
    def _dialog_start(self) -> str:
        if self._current_path is not None:
            return str(self._current_path.parent)
        return self._last_dir

    def _choose_files(self) -> None:
        if self._running:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("Pilih video"), self._dialog_start(), tr(FILE_DIALOG_FILTER)
        )
        if files:
            self._last_dir = str(Path(files[0]).parent)
            self._add_paths([Path(item) for item in files])

    def _choose_folder(self) -> None:
        if self._running:
            return
        folder = QFileDialog.getExistingDirectory(self, tr("Pilih folder video"), self._dialog_start())
        if folder:
            self._last_dir = folder
            self._add_paths([Path(folder)])

    def add_paths(self, paths: list[Path]) -> None:
        """Tambahkan video dari luar jendela (argumen CLI atau integrasi lain)."""

        self._add_paths(list(paths))

    def _paths_dropped(self, paths: list[str]) -> None:
        if self._running:
            QMessageBox.information(
                self,
                tr("Sedang memproses"),
                tr("Tunggu hingga proses selesai atau batalkan sebelum menambah video."),
            )
            return
        self._add_paths([Path(item) for item in paths])

    def _add_paths(self, paths: list[Path]) -> None:
        if self._running:
            return
        files: list[Path] = []
        rejected = 0
        folders_empty = 0
        for path in paths:
            try:
                path = path.expanduser()
                if path.is_dir():
                    found = scan_folder(path)
                    if not found:
                        folders_empty += 1
                    files.extend(found)
                elif path.is_file() and is_video_file(path):
                    files.append(path)
                else:
                    rejected += 1
            except OSError:
                rejected += 1

        if not files:
            if folders_empty and not rejected:
                QMessageBox.information(
                    self,
                    tr("Folder kosong"),
                    tr("Tidak ada berkas video yang didukung di folder tersebut."),
                )
            else:
                QMessageBox.warning(
                    self,
                    tr("Bukan video"),
                    tr("Pilih berkas video seperti MP4, MKV, MOV, WebM, atau AVI."),
                )
            return

        new_rows = self.queue_panel.model.add_paths(files)
        if not new_rows:
            self._set_footer("Semua video tersebut sudah ada di antrean")
            return

        if rejected or folders_empty:
            details = []
            if rejected:
                details.append(
                    tr(
                        "{n} berkas dilewati karena bukan video yang didukung.",
                        n=rejected,
                    )
                )
            if folders_empty:
                details.append(tr("{n} folder tidak berisi video.", n=folders_empty))
            QMessageBox.information(
                self, tr("Sebagian berkas dilewati"), "\n".join(details)
            )

        self._show_page(self.loaded_page)
        new_paths = [self.queue_panel.model.entry(row).path for row in new_rows]  # type: ignore[union-attr]
        self.queue_panel.select_path(new_paths[0])
        self._on_queue_current(new_paths[0])
        for path in new_paths:
            self._request_probe(path)
        self._set_footer(
            "{n} video di antrean",
            n=self.queue_panel.model.rowCount(),
        )
        self._update_actions()

    # ------------------------------------------------------------------ probe
    def _request_probe(self, path: Path, *, priority: bool = False) -> None:
        row = self.queue_panel.model.row_for_path(path)
        entry = self.queue_panel.model.entry(row) if row >= 0 else None
        if entry is None or entry.info is not None:
            return
        if path == self._probe_active_path:
            return
        if path in self._probe_queue:
            if priority:
                self._probe_queue.remove(path)
                self._probe_queue.appendleft(path)
            return
        if priority:
            self._probe_queue.appendleft(path)
        else:
            self._probe_queue.append(path)
        self._start_next_probe()

    def _start_next_probe(self) -> None:
        if self._probe_thread is not None:
            return
        while self._probe_queue:
            path = self._probe_queue.popleft()
            row = self.queue_panel.model.row_for_path(path)
            entry = self.queue_panel.model.entry(row) if row >= 0 else None
            if entry is None or entry.info is not None:
                continue
            self.queue_panel.model.update_entry(path, state="probing", detail="")
            self._probe_active_path = path
            self._probe_active_ok = False
            if not self._running:
                self._set_footer("Membaca metadata {name}…", name=path.name)

            thread = QThread(self)
            worker = ProbeWorker(path)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_probe_ok)
            worker.failed.connect(self._on_probe_error)
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda t=thread: self._on_probe_thread_finished(t))
            self._probe_thread = thread
            self._probe_worker = worker
            thread.start()
            return

    def _on_probe_ok(self, info: VideoInfo) -> None:
        self._probe_active_ok = True
        self.queue_panel.model.update_entry(
            info.path,
            info=info,
            state="ready",
            detail="",
            detail_kind="media",
        )
        if self._current_path == info.path and not self._running:
            self._show_video(info)
        self._update_actions()

    def _on_probe_error(self, title: str, detail: str) -> None:
        path = self._probe_active_path
        if path is None:
            return
        self.queue_panel.model.update_entry(path, state="error", detail=title)
        if self._current_path == path and not self._running and not self._closing:
            message, advice, technical = _split_detail(detail)
            QTimer.singleShot(
                0,
                lambda: show_error(self, title, message, advice, technical),
            )
        self._update_actions()

    def _on_probe_thread_finished(self, thread: QThread) -> None:
        if self._probe_thread is not thread:
            return
        active = self._probe_active_path
        ok = self._probe_active_ok
        self._probe_thread = None
        self._probe_worker = None
        self._probe_active_path = None

        if self._running:
            if self._batch_pending_path is not None and active == self._batch_pending_path:
                self._batch_pending_path = None
                self._run_next_item()
        elif self._current_path == active and ok and self._current_info is None:
            row = self.queue_panel.model.row_for_path(active)
            entry = self.queue_panel.model.entry(row) if row >= 0 else None
            if entry and entry.info:
                self._show_video(entry.info)
        self._start_next_probe()

    # ----------------------------------------------------------- queue events
    def _on_queue_current(self, path: object) -> None:
        if not isinstance(path, Path):
            return
        if self._running:
            return
        self._current_path = path
        row = self.queue_panel.model.row_for_path(path)
        entry = self.queue_panel.model.entry(row) if row >= 0 else None
        if entry is None:
            return
        self._show_page(self.loaded_page)
        if entry.info is not None:
            self._show_video(entry.info)
        else:
            self._current_info = None
            self.info_card.set_info(None)
            self.settings_panel.set_info(None)
            self.settings_panel.set_estimate(None)
            self.settings_panel.set_note("")
            self.settings_panel.clear_error()
            self._set_footer("Membaca metadata {name}…", name=path.name)
            self._request_probe(path, priority=True)
        self._update_actions()

    def _remove_path(self, path: Path) -> None:
        if self._running:
            return
        model = self.queue_panel.model
        row = model.row_for_path(path)
        if row < 0:
            return
        current_row = (
            model.row_for_path(self._current_path)
            if self._current_path is not None
            else -1
        )
        was_current = current_row == row
        fallback = model.entry(row + 1) or model.entry(row - 1)

        with contextlib.suppress(ValueError):
            self._probe_queue.remove(path)

        if model.remove_row(row) is None:
            return

        if model.rowCount() == 0:
            self._current_path = None
            self._current_info = None
            self.info_card.set_info(None)
            self.settings_panel.set_info(None)
            self.settings_panel.set_estimate(None)
            self.settings_panel.set_note("")
            self.settings_panel.clear_error()
            self.settings_panel.set_start_enabled(False)
            self._show_page(self.empty_page)
            self._set_footer("Antrean kosong — pilih video untuk memulai")
            self._update_actions()
            return

        if was_current:
            target = fallback if fallback is not None else model.entry(0)
            if target is not None:
                self.queue_panel.select_path(target.path)
                self._on_queue_current(target.path)
        elif self._current_path is not None:
            self.queue_panel.select_path(self._current_path)

        self._recalc_estimate()
        self._update_actions()
        self._set_footer(
            "Video dihapus · tersisa {n} video",
            n=model.rowCount(),
        )

    def _show_video(self, info: VideoInfo) -> None:
        self._current_path = info.path
        self._current_info = info
        self._show_page(self.loaded_page)
        self.info_card.set_info(info)
        self.settings_panel.set_info(info)
        if not self._running:
            self._set_footer("{name} · siap diekstrak", name=info.path.name)
        self._recalc_estimate()

    def _show_page(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)

    # --------------------------------------------------------------- estimate
    def _on_settings_changed(self) -> None:
        self.settings_panel.clear_error()
        self._recalc_estimate()

    def _recalc_estimate(self) -> None:
        if self._running:
            return
        model = self.queue_panel.model
        info = self._current_info
        if info is None:
            self.settings_panel.set_estimate(None)
            self.settings_panel.set_note("")
            self.settings_panel.set_start_enabled(False)
            self._update_actions()
            return
        try:
            options = self.settings_panel.options()
            points = plan_points(info, options)
            size = estimate_output_bytes(info, options, len(points))
            duration = self._estimate_extraction_seconds(info, options, len(points))
        except DomainError as exc:
            self.settings_panel.set_estimate(None)
            self.settings_panel.set_note("")
            self.settings_panel.set_error(exc.message)
            self.settings_panel.set_start_enabled(False)
            self._update_actions()
            return

        self.settings_panel.set_error("")
        self.settings_panel.set_estimate(len(points), size, duration)
        note = ""
        if info.duration_s > 2 * 3600:
            note = (
                "Video ini lebih dari 2 jam. Perkiraan waktu ekstraksi "
                "± {duration}; proses berjalan di latar belakang."
            )
            self.settings_panel.set_note(note, duration_s=duration)
        else:
            self.settings_panel.set_note("")
        self.settings_panel.set_start_enabled(model.has_pending())
        self._update_actions()

    @staticmethod
    def _estimate_extraction_seconds(
        info: VideoInfo, options: ExtractOptions, count: int
    ) -> float:
        start = max(0.0, min(options.start_s, info.duration_s))
        end = info.duration_s if options.end_s is None else min(options.end_s, info.duration_s)
        span = max(0.0, end - start)
        # Heuristik konservatif: dekode + encoding, bukan janji presisi.
        seconds = span * 0.015 + count * 0.012
        return max(1.0, seconds)

    # ------------------------------------------------------------ batch control
    def _start_batch(self) -> None:
        if self._running:
            return
        model = self.queue_panel.model
        if model.rowCount() == 0:
            self._set_footer("Tambahkan video terlebih dahulu")
            return

        try:
            options = self.settings_panel.options()
            if self._current_info is not None:
                plan_points(self._current_info, options)
        except DomainError as exc:
            self.settings_panel.set_error(exc.message)
            self._set_footer("Setelan belum valid")
            return

        if not model.prepare_run():
            self._set_footer(
                "Semua video di antrean sudah selesai — hapus lalu tambahkan lagi untuk mengulang"
            )
            self._recalc_estimate()
            return

        self._batch_options = options
        self._batch_results = []
        self._batch_errors = []
        self._error_shown = False
        self._cancel_requested = False
        self._batch_started = time.monotonic()
        self._current_total = 0
        self._current_done = 0
        self._eta_ema = None
        self._show_page(self.loaded_page)
        self._running = True
        self.settings_panel.set_running(True)
        self.queue_panel.set_running(True)
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_count_progress(0, 0, show_zero=True)
        self._set_eta("menghitung sisa waktu…")
        self._set_footer("Menyiapkan ekstraksi…")
        self._update_actions()
        self._run_next_item()

    def _run_next_item(self) -> None:
        if not self._running:
            return
        if self._cancel_requested:
            self._finish_batch(cancelled=True)
            return
        model = self.queue_panel.model
        chosen_row = -1
        for row in range(model.rowCount()):
            entry = model.entry(row)
            if entry and entry.state in ("waiting", "ready"):
                chosen_row = row
                break
        if chosen_row < 0:
            self._finish_batch()
            return

        entry = model.entry(chosen_row)
        assert entry is not None
        self._current_path = entry.path
        self._current_info = entry.info
        self.queue_panel.select_path(entry.path)
        self.info_card.set_info(entry.info)
        self.settings_panel.set_info(entry.info)

        if entry.info is None:
            model.update_entry(entry.path, state="probing", detail="")
            self._batch_pending_path = entry.path
            self._set_footer("Membaca metadata {name}…", name=entry.path.name)
            self._request_probe(entry.path, priority=True)
            return

        self._launch_extraction(entry.path, entry.info)

    def _launch_extraction(self, path: Path, info: VideoInfo) -> None:
        options = self._batch_options
        if options is None:
            self._finish_batch(cancelled=True)
            return
        self.queue_panel.model.update_entry(path, state="running", detail="")
        self._current_total = 0
        self._current_done = 0
        self._eta_ema = None
        self._item_started = time.monotonic()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_count_progress(0, 0, show_zero=True)
        self._set_eta("menghitung sisa waktu…")
        self._set_footer("Mengekstrak {name}…", name=path.name)

        thread = QThread(self)
        worker = ExtractWorker(info, options, engine="auto")
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.stage.connect(self._on_stage)
        worker.finished.connect(self._on_item_finished)
        worker.failed.connect(self._on_item_failed)
        worker.cancelled.connect(self._on_item_cancelled)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self._on_extract_thread_finished(t))
        self._extract_thread = thread
        self._extract_worker = worker
        thread.start()

    def _on_extract_thread_finished(self, thread: QThread) -> None:
        if self._extract_thread is thread:
            self._extract_thread = None
            self._extract_worker = None

    def _on_progress(self, done: int, total: int, ts: float) -> None:
        if total <= 0:
            return
        self._current_total = total
        self._current_done = max(self._current_done, done)
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(self._current_done)
        self._set_count_progress(self._current_done, total)
        elapsed = max(0.001, time.monotonic() - self._item_started)
        if done > 0:
            raw = elapsed / done * (total - done)
            self._eta_ema = raw if self._eta_ema is None else (0.7 * self._eta_ema + 0.3 * raw)
            self._set_eta(seconds=self._eta_ema)
        else:
            self._set_eta("menghitung sisa waktu…")

    def _on_stage(self, stage: str) -> None:
        name = self._current_path.name if self._current_path else "video"
        if stage == "memeriksa":
            self._set_footer("Memeriksa {name}…", name=name)
        elif stage == "mengekstrak":
            self._set_footer("Mengekstrak {name}…", name=name)
        elif stage == "menyimpan":
            self._set_footer("Menyimpan hasil…")

    def _on_item_finished(self, results: list) -> None:
        if self._closing:
            return
        path = self._current_path
        if path is None:
            self._run_next_item()
            return
        entries = [item for item in results if isinstance(item, FrameResult)]
        self.queue_panel.model.update_entry(
            path,
            state="done",
            detail="",
            detail_kind="done",
            results=entries,
        )
        self._batch_results.extend(entries)
        log.info("Item selesai: %s (%d gambar)", path.name, len(entries))
        if self._cancel_requested:
            self._finish_batch(cancelled=True)
            return
        self._run_next_item()

    def _on_item_failed(self, title: str, detail: str) -> None:
        if self._closing:
            return
        path = self._current_path
        worker_results = self._extract_worker.last_results if self._extract_worker else []
        if path is not None:
            self.queue_panel.model.update_entry(
                path, state="error", detail=title, results=list(worker_results)
            )
            self._batch_errors.append((path.name, title, detail))
            self._batch_results.extend(worker_results)
        if not self._error_shown:
            self._error_shown = True
            message, advice, technical = _split_detail(detail)
            if worker_results:
                message += "\n\n" + tr(
                    "{n} gambar yang sudah selesai tetap tersimpan.",
                    n=len(worker_results),
                )
            show_error(self, title, message, advice, technical)
        self._run_next_item()

    def _on_item_cancelled(self, count: int) -> None:
        if self._closing:
            return
        path = self._current_path
        results = self._extract_worker.last_results if self._extract_worker else []
        if path is not None:
            self.queue_panel.model.update_entry(
                path,
                state="cancelled",
                detail="",
                detail_kind="cancelled",
                detail_args={"saved": count, "total": self._current_total},
                results=list(results),
            )
            self._batch_results.extend(results)
        self._cancel_requested = True
        self._finish_batch(cancelled=True)

    def _request_cancel(self) -> None:
        if not self._running or self._cancel_requested:
            return
        self._cancel_requested = True
        self.cancel_button.setEnabled(False)
        self._set_eta("menghentikan…")
        self._set_footer("Membatalkan ekstraksi…")
        if self._extract_worker is not None:
            self._extract_worker.request_cancel()
        if self._batch_pending_path is not None:
            self._set_footer("Membatalkan…")

    def _finish_batch(self, *, cancelled: bool = False) -> None:
        if not self._running:
            return
        cancelled = cancelled or self._cancel_requested
        self._running = False
        self.settings_panel.set_running(False)
        self.queue_panel.set_running(False)
        self.cancel_button.hide()
        self.cancel_button.setEnabled(True)
        self._cancel_requested = False
        self._batch_pending_path = None

        model = self.queue_panel.model
        if cancelled:
            for entry in model.entries():
                if entry.state in ("waiting", "ready", "probing"):
                    model.update_entry(
                        entry.path,
                        state="cancelled",
                        detail="",
                        detail_kind="not_run",
                    )

        elapsed = max(0.0, time.monotonic() - self._batch_started)
        results = list(self._batch_results)
        total_size = sum(item.size_bytes for item in results)

        if self._closing:
            self._update_actions()
            return

        if results:
            self.gallery.set_results(
                results,
                elapsed,
                expected_total=self._current_total if cancelled else None,
                cancelled=cancelled,
            )
            self._show_page(self.gallery)
        elif cancelled:
            self._show_page(self.loaded_page)
        else:
            self._show_page(self.loaded_page)

        if cancelled:
            if results:
                self._set_footer(
                    "Dibatalkan · {n} gambar tersimpan",
                    n=len(results),
                )
            else:
                self._set_footer("Dibatalkan · tidak ada gambar tersimpan")
            self._set_count_progress(self._current_done, self._current_total)
            self._set_eta("dibatalkan")
        elif self._batch_errors:
            if results:
                self._set_footer(
                    "Selesai dengan galat: {errors} · {n} gambar",
                    errors=len(self._batch_errors),
                    n=len(results),
                )
            else:
                self._set_footer("Ekstraksi gagal · lihat pesan galat")
            self._set_eta("selesai dengan galat")
            if not self._error_shown:
                name, title, detail = self._batch_errors[0]
                message, advice, technical = _split_detail(detail)
                self._error_shown = True
                show_error(
                    self,
                    f"{tr(title)} — {name}",
                    message,
                    advice,
                    technical,
                )
        else:
            self._set_footer(
                "Selesai · {n} gambar · {size}",
                n=len(results),
                size_bytes=total_size,
            )
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self._set_count_total(len(results))
            self._set_eta("selesai")

        self._recalc_estimate()
        self._update_actions()

    # ----------------------------------------------------------------- results
    def _open_results_folder(self) -> None:
        folder = self.gallery.folder()
        if folder is None:
            if self._current_path is not None:
                folder = self._current_path.parent
            else:
                return
        if not folder.exists():
            QMessageBox.warning(
                self,
                tr("Folder tidak ditemukan"),
                tr("Folder hasil tidak lagi tersedia:\n{folder}", folder=folder),
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ------------------------------------------------------------------ footer
    def _set_footer(self, source: str, **kwargs: object) -> None:
        self._footer_source = source
        self._footer_kwargs = dict(kwargs)
        self._render_footer()

    def _render_footer(self) -> None:
        values = dict(self._footer_kwargs)
        if "size_bytes" in values:
            values["size"] = human_bytes(float(values.pop("size_bytes")), language())
        if "duration_s" in values:
            values["duration"] = human_duration(
                float(values.pop("duration_s")), language()
            )
        text = tr(self._footer_source, **values) if self._footer_source else ""
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

    def _set_eta(self, source: str | None = None, *, seconds: float | None = None) -> None:
        self._eta_source = source or ""
        self._eta_seconds = seconds
        self._render_eta()

    def _render_eta(self) -> None:
        if self._eta_seconds is not None:
            text = eta_text(self._eta_seconds, language())
        elif self._eta_source:
            text = tr(self._eta_source)
        else:
            text = ""
        self.eta_label.setText(text)

    def _set_count_progress(
        self, current: int, total: int, *, show_zero: bool = False
    ) -> None:
        self._count_current = int(current)
        self._count_total = int(total)
        self._count_total_only = False
        self._count_show_zero = show_zero
        self._render_count()

    def _set_count_total(self, total: int) -> None:
        self._count_total = int(total)
        self._count_current = int(total)
        self._count_total_only = True
        self._count_show_zero = False
        self._render_count()

    def _render_count(self) -> None:
        if self._count_total_only:
            text = format_count(self._count_total)
        elif self._count_total:
            text = (
                f"{format_count(self._count_current)}/"
                f"{format_count(self._count_total)}"
            )
        elif self._count_show_zero:
            text = "0"
        else:
            text = ""
        self.count_label.setText(text)

    def _update_actions(self) -> None:
        self.open_action.setEnabled(not self._running)
        self.add_action.setEnabled(not self._running)
        self.start_action.setEnabled(
            not self._running and self.settings_panel.start_button.isEnabled()
        )
        self.cancel_action.setEnabled(self._running)
        self.open_folder_action.setEnabled(
            not self._running and self.gallery.model.rowCount() > 0
        )
        self.dark_action.setChecked(self._theme == "dark")

    # -------------------------------------------------------------------- info
    def _show_shortcuts(self) -> None:
        rows = [
            ("Ctrl+O", "Buka video"),
            ("Ctrl+Shift+O", "Tambah video ke antrean"),
            ("Delete", "Hapus video terpilih dari antrean"),
            ("Ctrl+Enter", "Mulai ekstraksi"),
            ("Esc", "Batalkan ekstraksi"),
            ("Ctrl+Shift+L", "Buka/tutup panel log"),
            ("Ctrl+Q", "Keluar"),
        ]
        body = "".join(
            f"<tr><td><b>{shortcut}</b></td><td>{tr(label)}</td></tr>"
            for shortcut, label in rows
        )
        QMessageBox.information(
            self,
            tr("Pintasan keyboard"),
            f"<b>{tr('Pintasan keyboard')}</b><br><br>"
            f"<table cellspacing='6'>{body}</table>",
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("Tentang {name}", name=APP_NAME),
            f"<h3>{APP_NAME} {__version__}</h3>"
            f"<p>{tr('Ekstrak frame dari video menjadi PNG atau JPG.')}</p>"
            f"<p>{tr('Lisensi aplikasi: MIT. Antarmuka memakai Qt for Python (PySide6, LGPLv3). Mesin ekstraksi memakai ffmpeg (LGPL) dan OpenCV (Apache 2.0).')}</p>"
            f"<p>{tr('Log: {path}', path=get_log_path())}</p>",
        )

    # ---------------------------------------------------------------- settings
    def _restore_settings(self) -> None:
        theme = str(self.settings.value("theme", "dark"))
        self._theme = "light" if theme == "light" else "dark"
        geometry = self.settings.value("geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        self._last_dir = str(self.settings.value("last_dir", str(Path.home())))
        self.settings_panel.load_settings(self.settings)

    def _save_settings(self) -> None:
        self.settings_panel.save_settings(self.settings)
        self.settings.setValue("theme", self._theme)
        self.settings.setValue("language", language())
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("last_dir", self._last_dir)
        self.settings.sync()

    # ------------------------------------------------------------------- close
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._running:
            answer = QMessageBox.question(
                self,
                tr("Ekstraksi sedang berjalan"),
                tr(
                    "Hentikan ekstraksi dan keluar?\n\n"
                    "Gambar yang sudah tersimpan tidak akan dihapus."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._request_cancel()

        # ``_running`` bisa sudah False ketika worker selesai, tetapi QThread
        # masih hidup sebentar. Jangan biarkan jendela dihancurkan bersama
        # thread yang belum berhenti.
        if self._extract_thread is not None or self._running:
            self._closing = True
            deadline = time.monotonic() + 6.0
            while self._extract_thread is not None and time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.02)
            if self._extract_thread is not None:
                log.warning("Thread ekstraksi belum berhenti saat jendela ditutup.")
                self._extract_thread.terminate()
                self._extract_thread.wait(800)
                self._extract_thread = None
                self._extract_worker = None

        if self._probe_thread is not None:
            self._probe_thread.quit()
            if not self._probe_thread.wait(800):
                self._probe_thread.terminate()
                self._probe_thread.wait(500)
            self._probe_thread = None

        self.gallery.shutdown()
        self._save_settings()
        if getattr(self, "_log_handler", None) is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None
        super().closeEvent(event)

    # -------------------------------------------------------------- drag/drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        if self._running:
            self._paths_dropped([])
            event.ignore()
            return
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile()
        ]
        if paths:
            event.acceptProposedAction()
            self._paths_dropped(paths)
        else:
            event.ignore()


__all__ = ["MainWindow"]
