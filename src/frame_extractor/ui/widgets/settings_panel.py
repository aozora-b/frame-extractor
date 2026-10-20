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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Setelan")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.mode_combo = QComboBox()
        for value, label in MODE_LABELS:
            self.mode_combo.addItem(label, value)
        self.mode_combo.setAccessibleName("Mode pengambilan frame")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._labelled("Mode", self.mode_combo))
        self._controls.append(self.mode_combo)

        self.mode_stack = QStackedWidget()
        self.mode_stack.setSizePolicy(
            self.mode_stack.sizePolicy().horizontalPolicy(),
            self.mode_stack.sizePolicy().verticalPolicy(),
        )
        self.interval_spin = self._double_spin(0.05, 86_400.0, 1.0, 2, " dtk")
        self.interval_spin.setToolTip("Ambil satu frame setiap N detik")
        self.count_spin = self._int_spin(1, 200_000, 30)
        self.count_spin.setToolTip("Jumlah frame yang disebar merata sepanjang video")
        self.start_spin = self._double_spin(0.0, 86_400.0, 0.0, 2, " dtk")
        self.end_spin = self._double_spin(0.01, 86_400.0, 10.0, 2, " dtk")
        self.start_spin.setToolTip("Awal rentang yang diambil")
        self.end_spin.setToolTip("Akhir rentang (tidak termasuk)")

        self.mode_stack.addWidget(self._inline("Tiap", self.interval_spin))
        self.mode_stack.addWidget(self._inline("Jumlah", self.count_spin))
        self.mode_stack.addWidget(self._range_widget())
        layout.addWidget(self.mode_stack)
        self._controls.extend([self.interval_spin, self.count_spin, self.start_spin, self.end_spin])

        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG — lossless", "png")
        self.format_combo.addItem("JPG — lebih kecil", "jpg")
        self.format_combo.setAccessibleName("Format gambar")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        layout.addWidget(self._labelled("Format", self.format_combo))
        self._controls.append(self.format_combo)

        self.quality_widget = QWidget()
        quality_layout = QVBoxLayout(self.quality_widget)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.setSpacing(4)
        quality_header = QHBoxLayout()
        quality_label = QLabel("Kualitas JPG")
        quality_label.setObjectName("Muted")
        quality_header.addWidget(quality_label)
        quality_header.addStretch(1)
        self.quality_spin = self._int_spin(1, 100, 95)
        self.quality_spin.setFixedWidth(72)
        self.quality_spin.setAccessibleName("Kualitas JPEG")
        quality_header.addWidget(self.quality_spin)
        quality_layout.addLayout(quality_header)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        self.quality_slider.setAccessibleName("Slider kualitas JPEG")
        self.quality_slider.setMinimumHeight(24)
        quality_layout.addWidget(self.quality_slider)
        layout.addWidget(self.quality_widget)
        self._controls.extend([self.quality_slider, self.quality_spin])

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Di samping berkas video")
        self.out_edit.setClearButtonEnabled(True)
        self.out_edit.setAccessibleName("Folder keluaran")
        self.out_edit.setToolTip("Kosongkan untuk menyimpan di folder yang sama dengan video")
        self.out_edit.editingFinished.connect(self._emit_changed)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(self.out_edit, 1)
        self.browse_button = QToolButton()
        self.browse_button.setText("…")
        self.browse_button.setToolTip("Pilih folder keluaran")
        self.browse_button.setAccessibleName("Pilih folder keluaran")
        self.browse_button.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.browse_button)
        layout.addWidget(self._labelled("Folder keluaran", self._make_row(folder_row), top=True))
        self._controls.extend([self.out_edit, self.browse_button])

        separator = QFrame()
        separator.setObjectName("Separator")
        layout.addWidget(separator)

        estimate_caption = QLabel("PERKIRAAN")
        estimate_caption.setObjectName("StatCaption")
        layout.addWidget(estimate_caption)
        self.estimate_number = QLabel("—")
        self.estimate_number.setObjectName("EstimateNumber")
        layout.addWidget(self.estimate_number)
        self.estimate_detail = QLabel("Pilih video untuk melihat perkiraan.")
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

        self.start_button = QPushButton("Mulai ekstraksi")
        self.start_button.setObjectName("Primary")
        self.start_button.setToolTip("Mulai mengekstrak semua video di antrean (Ctrl+Enter)")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.startRequested)
        layout.addWidget(self.start_button)

        hint = QLabel("Ctrl+Enter untuk mulai · Esc untuk membatalkan")
        hint.setObjectName("StatCaption")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.quality_slider.valueChanged.connect(self._on_quality_slider)
        self.quality_spin.valueChanged.connect(self._on_quality_spin)
        self.interval_spin.valueChanged.connect(self._emit_changed)
        self.count_spin.valueChanged.connect(self._emit_changed)
        self.start_spin.valueChanged.connect(self._emit_changed)
        self.end_spin.valueChanged.connect(self._emit_changed)
        self._sync_mode()
        self._sync_quality()

    # ---------------------------------------------------------------- helpers
    def _labelled(self, text: str, widget: QWidget, *, top: bool = False) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container) if top else QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if top else 8)
        label = QLabel(text)
        label.setObjectName("Muted")
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
        label = QLabel(label_text)
        label.setObjectName("Muted")
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
        start_label = QLabel("Mulai")
        start_label.setObjectName("Muted")
        start_label.setBuddy(self.start_spin)
        end_label = QLabel("Selesai")
        end_label.setObjectName("Muted")
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
        spin.setMinimumHeight(32)
        return spin

    def _int_spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        spin.setAccelerated(True)
        spin.setMinimumHeight(32)
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
        self.start_button.setText("Memproses…" if running else "Mulai ekstraksi")
        self.error_label.setVisible(False if running else self.error_label.isVisible())

    def set_start_enabled(self, enabled: bool) -> None:
        self._start_ready = bool(enabled)
        self.start_button.setEnabled(self._start_ready and not self._running)

    def set_estimate(
        self,
        count: int | None,
        size_bytes: int | None = None,
        duration_s: float | None = None,
    ) -> None:
        if count is None:
            self.estimate_number.setText("—")
            self.estimate_detail.setText("Pilih video untuk melihat perkiraan.")
            return
        self.estimate_number.setText(f"{count:,} gambar".replace(",", "."))
        parts = []
        if size_bytes:
            parts.append(f"± {human_bytes(size_bytes)}")
        if duration_s:
            parts.append(f"± {human_duration(duration_s)}")
        self.estimate_detail.setText(" · ".join(parts) if parts else "Siap diekstrak.")

    def set_note(self, text: str) -> None:
        self.note_label.setText(text)
        self.note_label.setVisible(bool(text))

    def set_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))

    def clear_error(self) -> None:
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
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder keluaran", start)
        if folder:
            self.out_edit.setText(folder)
            self._emit_changed()


__all__ = ["SettingsPanel", "Mode", "Format"]
