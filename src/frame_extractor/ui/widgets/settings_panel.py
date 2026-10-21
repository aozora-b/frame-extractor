"""Panel setelan di sisi kanan jendela."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...core.errors import InvalidOptionError
from ...core.humanize import human_bytes, human_duration
from ...core.models import ExtractOptions, Format, Mode, VideoInfo
from ..i18n import language, tr, translate_message

DEFAULT_TEMPLATE = "{stem}_{index:06d}_{time}.{ext}"

MODE_LABELS: tuple[tuple[str, str], ...] = (
    ("interval", "Satu frame tiap N detik"),
    ("count", "N frame tersebar merata"),
    ("range", "Rentang waktu tertentu"),
)


class SettingsPanel(QFrame):
    settingsChanged = Signal()
    startRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedWidth(360)
        self._info: VideoInfo | None = None
        self._loading = False
        self._running = False
        self._start_ready = False
        self._controls: list[QWidget] = []
        self._labels: list[tuple[QLabel, str]] = []
        self._estimate_count: int | None = None
        self._estimate_size: int | None = None
        self._estimate_duration: float | None = None
        self._note_source = ""
        self._note_kwargs: dict[str, object] = {}
        self._error_source = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("SettingsScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        content = QWidget()
        content.setObjectName("SettingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 12)
        layout.setSpacing(12)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area, 1)

        title = self._label("Setelan", "SectionTitle")
        layout.addWidget(title)

        self.mode_combo = QComboBox()
        self.mode_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.mode_combo.setMinimumContentsLength(18)
        for value, label in MODE_LABELS:
            self.mode_combo.addItem(tr(label), value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._labelled("Mode", self.mode_combo, top=True))
        self._controls.append(self.mode_combo)

        self.mode_stack = QStackedWidget()
        self.mode_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.mode_stack.setMinimumHeight(76)
        self.interval_spin = self._double_spin(0.05, 86_400.0, 1.0, 2, " dtk")
        self.count_spin = self._int_spin(1, 200_000, 30)
        self.start_spin = self._double_spin(0.0, 86_400.0, 0.0, 2, " dtk")
        self.end_spin = self._double_spin(0.01, 86_400.0, 10.0, 2, " dtk")

        self.mode_stack.addWidget(self._inline("Tiap", self.interval_spin))
        self.mode_stack.addWidget(self._inline("Jumlah", self.count_spin))
        self.mode_stack.addWidget(self._range_widget())
        layout.addWidget(self.mode_stack)
        self._controls.extend([self.interval_spin, self.count_spin, self.start_spin, self.end_spin])

        self.format_combo = QComboBox()
        self.format_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.format_combo.setMinimumContentsLength(16)
        self.format_combo.addItem(tr("PNG — lossless"), "png")
        self.format_combo.addItem(tr("JPG — lebih kecil"), "jpg")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        layout.addWidget(self._labelled("Format", self.format_combo, top=True))
        self._controls.append(self.format_combo)

        self.quality_widget = QWidget()
        quality_layout = QVBoxLayout(self.quality_widget)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.setSpacing(4)
        quality_header = QHBoxLayout()
        quality_label = self._label("Kualitas JPG", "Muted")
        quality_header.addWidget(quality_label)
        quality_header.addStretch(1)
        self.quality_spin = self._int_spin(1, 100, 95)
        self.quality_spin.setFixedWidth(80)
        quality_header.addWidget(self.quality_spin)
        quality_layout.addLayout(quality_header)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        self.quality_slider.setMinimumHeight(24)
        quality_layout.addWidget(self.quality_slider)
        layout.addWidget(self.quality_widget)
        self._controls.extend([self.quality_slider, self.quality_spin])

        self.out_edit = QLineEdit()
        self.out_edit.setClearButtonEnabled(True)
        self.out_edit.editingFinished.connect(self._emit_changed)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.out_edit, 1)
        self.browse_button = QToolButton()
        self.browse_button.setText("…")
        self.browse_button.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.browse_button)
        layout.addWidget(self._labelled("Folder keluaran", self._make_row(folder_row), top=True))
        self._controls.extend([self.out_edit, self.browse_button])

        separator = QFrame()
        separator.setObjectName("Separator")
        layout.addWidget(separator)

        estimate_caption = self._label("PERKIRAAN", "StatCaption")
        layout.addWidget(estimate_caption)
        self.estimate_number = QLabel("—")
        self.estimate_number.setObjectName("EstimateNumber")
        layout.addWidget(self.estimate_number)
        self.estimate_detail = QLabel()
        self.estimate_detail.setObjectName("Muted")
        self.estimate_detail.setWordWrap(True)
        layout.addWidget(self.estimate_detail)

        self.note_label = QLabel()
        self.note_label.setObjectName("Warning")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        layout.addWidget(self.note_label)

        self.error_label = QLabel()
        self.error_label.setObjectName("InlineError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        layout.addStretch(1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 18)
        footer_layout.setSpacing(8)

        self.start_button = QPushButton()
        self.start_button.setObjectName("Primary")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.startRequested)
        footer_layout.addWidget(self.start_button)

        hint = self._label("Ctrl+Enter untuk mulai · Esc untuk membatalkan", "StatCaption")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        footer_layout.addWidget(hint)

        outer.addWidget(footer)

        self.quality_slider.valueChanged.connect(self._on_quality_slider)
        self.quality_spin.valueChanged.connect(self._on_quality_spin)
        self.interval_spin.valueChanged.connect(self._emit_changed)
        self.count_spin.valueChanged.connect(self._emit_changed)
        self.start_spin.valueChanged.connect(self._emit_changed)
        self.end_spin.valueChanged.connect(self._emit_changed)
        self._sync_mode()
        self._sync_quality()
        self.retranslate()

    def retranslate(self) -> None:
        for label, source in self._labels:
            label.setText(tr(source))
        for index, (_, source) in enumerate(MODE_LABELS):
            self.mode_combo.setItemText(index, tr(source))
        self.format_combo.setItemText(0, tr("PNG — lossless"))
        self.format_combo.setItemText(1, tr("JPG — lebih kecil"))
        self.mode_combo.setAccessibleName(tr("Mode pengambilan frame"))
        self.format_combo.setAccessibleName(tr("Format gambar"))
        self.interval_spin.setToolTip(tr("Ambil satu frame setiap N detik"))
        self.count_spin.setToolTip(
            tr("Jumlah frame yang disebar merata sepanjang video")
        )
        self.start_spin.setToolTip(tr("Awal rentang yang diambil"))
        self.end_spin.setToolTip(tr("Akhir rentang (tidak termasuk)"))
        for spin in (self.interval_spin, self.start_spin, self.end_spin):
            spin.setSuffix(tr(" dtk"))
        self.quality_spin.setAccessibleName(tr("Kualitas JPEG"))
        self.quality_slider.setAccessibleName(tr("Slider kualitas JPEG"))
        self.out_edit.setPlaceholderText(tr("Di samping berkas video"))
        self.out_edit.setAccessibleName(tr("Folder keluaran"))
        self.out_edit.setToolTip(
            tr("Kosongkan untuk menyimpan di folder yang sama dengan video")
        )
        self.browse_button.setToolTip(tr("Pilih folder keluaran"))
        self.browse_button.setAccessibleName(tr("Pilih folder keluaran"))
        self.start_button.setToolTip(
            tr("Mulai mengekstrak semua video di antrean (Ctrl+Enter)")
        )
        self._render_start_button()
        self._render_estimate()
        self._render_note()
        self._render_error()

    # ---------------------------------------------------------------- helpers
    def _label(self, text: str, object_name: str | None = None) -> QLabel:
        label = QLabel()
        if object_name:
            label.setObjectName(object_name)
        self._labels.append((label, text))
        label.setText(tr(text))
        return label

    def _labelled(self, text: str, widget: QWidget, *, top: bool = False) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container) if top else QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if top else 8)
        label = self._label(text, "Muted")
        label.setBuddy(widget)
        if top:
            layout.addWidget(label)
            layout.addWidget(widget)
        else:
            layout.addWidget(label)
            layout.addWidget(widget, 1)
        return container

    def _make_row(self, layout) -> QWidget:  # noqa: ANN001
        container = QWidget()
        container.setLayout(layout)
        return container

    def _inline(self, label_text: str, spin: QWidget) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = self._label(label_text, "Muted")
        label.setBuddy(spin)
        row.addWidget(label)
        row.addWidget(spin, 1)
        return container

    def _range_widget(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        start_label = self._label("Mulai", "Muted")
        start_label.setBuddy(self.start_spin)
        end_label = self._label("Akhir", "Muted")
        end_label.setBuddy(self.end_spin)
        grid.addWidget(start_label, 0, 0)
        grid.addWidget(self.start_spin, 0, 1)
        grid.addWidget(end_label, 1, 0)
        grid.addWidget(self.end_spin, 1, 1)
        return container

    def _double_spin(
        self,
        minimum: float,
        maximum: float,
        value: float,
        decimals: int,
        suffix: str,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        spin.setAccelerated(True)
        spin.setMinimumHeight(36)
        spin.setMinimumWidth(132)
        spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return spin

    def _int_spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        spin.setAccelerated(True)
        spin.setMinimumHeight(36)
        spin.setMinimumWidth(100)
        spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return spin

    # ----------------------------------------------------------------- signals
    def _emit_changed(self, *args) -> None:  # noqa: ANN002
        if not self._loading:
            self.settingsChanged.emit()

    def _on_mode_changed(self, *args) -> None:  # noqa: ANN002
        self._sync_mode()
        self._emit_changed()

    def _on_format_changed(self, *args) -> None:  # noqa: ANN002
        self._sync_quality()
        self._emit_changed()

    def _on_quality_slider(self, value: int) -> None:
        if self.quality_spin.value() != value:
            self.quality_spin.blockSignals(True)
            self.quality_spin.setValue(value)
            self.quality_spin.blockSignals(False)
        self._emit_changed()

    def _on_quality_spin(self, value: int) -> None:
        if self.quality_slider.value() != value:
            self.quality_slider.blockSignals(True)
            self.quality_slider.setValue(value)
            self.quality_slider.blockSignals(False)
        self._emit_changed()

    def _sync_mode(self) -> None:
        mode = self.mode_combo.currentData()
        index = {"interval": 0, "count": 1, "range": 2}.get(str(mode), 0)
        self.mode_stack.setCurrentIndex(index)

    def _sync_quality(self) -> None:
        self.quality_widget.setVisible(self.format_combo.currentData() == "jpg")

    # -------------------------------------------------------------------- state
    def mode(self) -> str:
        return str(self.mode_combo.currentData())

    def options(self) -> ExtractOptions:
        mode = self.mode()
        out_text = self.out_edit.text().strip()
        try:
            out_dir = Path(out_text).expanduser() if out_text else None
        except (ValueError, OSError) as exc:
            raise InvalidOptionError("Folder keluaran tidak valid.", detail=str(exc)) from exc
        fmt = str(self.format_combo.currentData())
        return ExtractOptions(
            mode=mode,  # type: ignore[arg-type]
            interval_s=float(self.interval_spin.value()),
            frame_total=int(self.count_spin.value()),
            start_s=float(self.start_spin.value()),
            end_s=float(self.end_spin.value()),
            fmt=fmt,  # type: ignore[arg-type]
            quality=int(self.quality_spin.value()),
            out_dir=out_dir,
            template=DEFAULT_TEMPLATE,
        )

    def set_info(self, info: VideoInfo | None) -> None:
        self._info = info
        if info is None:
            return
        duration = max(0.01, float(info.duration_s))
        self._loading = True
        try:
            self.start_spin.setMaximum(duration)
            self.end_spin.setMaximum(duration)
            if self.start_spin.value() >= duration:
                self.start_spin.setValue(0.0)
            if self.end_spin.value() <= self.start_spin.value() or self.end_spin.value() > duration:
                self.end_spin.setValue(duration)
        finally:
            self._loading = False

    def set_running(self, running: bool) -> None:
        self._running = running
        for control in self._controls:
            control.setEnabled(not running)
        self.start_button.setEnabled(not running and self._start_ready)
        self._render_start_button()
        if running:
            self.error_label.hide()
        else:
            self._render_error()

    def _render_start_button(self) -> None:
        self.start_button.setText(
            tr("Memproses…") if self._running else tr("Mulai ekstraksi")
        )

    def set_start_enabled(self, enabled: bool) -> None:
        self._start_ready = bool(enabled)
        self.start_button.setEnabled(self._start_ready and not self._running)

    def set_estimate(
        self,
        count: int | None,
        size_bytes: int | None = None,
        duration_s: float | None = None,
    ) -> None:
        self._estimate_count = count
        self._estimate_size = size_bytes
        self._estimate_duration = duration_s
        self._render_estimate()

    def _render_estimate(self) -> None:
        count = self._estimate_count
        if count is None:
            self.estimate_number.setText("—")
            self.estimate_detail.setText(tr("Pilih video untuk melihat perkiraan."))
            return
        self.estimate_number.setText(tr("{n} gambar", n=count))
        parts = []
        if self._estimate_size:
            parts.append(f"± {human_bytes(self._estimate_size, language())}")
        if self._estimate_duration:
            parts.append(f"± {human_duration(self._estimate_duration, language())}")
        self.estimate_detail.setText(" · ".join(parts) if parts else tr("Siap diekstrak."))

    def set_note(self, text: str, **kwargs: object) -> None:
        self._note_source = text
        self._note_kwargs = dict(kwargs)
        self._render_note()

    def _render_note(self) -> None:
        if self._note_source:
            values = dict(self._note_kwargs)
            if "duration_s" in values:
                values["duration"] = human_duration(
                    float(values.pop("duration_s")), language()
                )
            text = tr(self._note_source, **values)
        else:
            text = ""
        self.note_label.setText(text)
        self.note_label.setVisible(bool(text))

    def set_error(self, text: str) -> None:
        self._error_source = text
        self._render_error()

    def _render_error(self) -> None:
        text = translate_message(self._error_source) if self._error_source else ""
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text) and not self._running)

    def clear_error(self) -> None:
        self._error_source = ""
        self.error_label.clear()
        self.error_label.hide()

    # ---------------------------------------------------------------- settings
    def load_settings(self, settings: QSettings) -> None:
        self._loading = True
        try:
            mode = str(settings.value("mode", "interval"))
            index = self.mode_combo.findData(mode)
            self.mode_combo.setCurrentIndex(index if index >= 0 else 0)
            self.interval_spin.setValue(float(settings.value("interval", 1.0)))
            self.count_spin.setValue(int(settings.value("count", 30)))
            self.start_spin.setValue(float(settings.value("range_start", 0.0)))
            self.end_spin.setValue(float(settings.value("range_end", 10.0)))
            fmt = str(settings.value("format", "png"))
            fmt_index = self.format_combo.findData(fmt)
            self.format_combo.setCurrentIndex(fmt_index if fmt_index >= 0 else 0)
            self.quality_spin.setValue(int(settings.value("quality", 95)))
            self.out_edit.setText(str(settings.value("out_dir", "") or ""))
            self._sync_mode()
            self._sync_quality()
        finally:
            self._loading = False

    def save_settings(self, settings: QSettings) -> None:
        settings.setValue("mode", self.mode())
        settings.setValue("interval", self.interval_spin.value())
        settings.setValue("count", self.count_spin.value())
        settings.setValue("range_start", self.start_spin.value())
        settings.setValue("range_end", self.end_spin.value())
        settings.setValue("format", str(self.format_combo.currentData()))
        settings.setValue("quality", self.quality_spin.value())
        settings.setValue("out_dir", self.out_edit.text().strip())

    # ------------------------------------------------------------------ folder
    def _browse_folder(self) -> None:
        start = self.out_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, tr("Pilih folder keluaran"), start)
        if folder:
            self.out_edit.setText(folder)
            self._emit_changed()


__all__ = ["SettingsPanel", "Mode", "Format"]
