"""Galeri hasil dengan thumbnail yang dimuat bertahap di thread pool."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ...core.humanize import human_bytes, human_duration
from ...core.models import FrameResult
from ..i18n import format_count, language, tr
from ..models import ResultsModel, ThumbnailSignals, ThumbnailTask
from ..theme import PALETTES

THUMB_SIZE = QSize(240, 135)
GRID_SIZE = QSize(190, 150)


def _tokens() -> dict[str, str]:
    app = QApplication.instance()
    name = app.property("themeName") if app else "dark"
    return PALETTES["light" if name == "light" else "dark"]


class ResultsDelegate(QStyledItemDelegate):
    """Gambar thumbnail dan nama berkas dengan ukuran yang dapat diprediksi."""

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return GRID_SIZE

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        tokens = _tokens()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect).adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hover:
            color = QColor(tokens["selection"] if selected else tokens["surface_alt"])
            if selected:
                color.setAlpha(170)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 8, 8)

        thumb = QRectF(rect.left(), rect.top() + 3, rect.width(), rect.width() * 9 / 16)
        pixmap = index.data(int(Qt.ItemDataRole.DecorationRole))
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(thumb, 6, 6)
            painter.setClipPath(path)
            painter.drawPixmap(thumb, pixmap, QRectF(pixmap.rect()))
            painter.setClipping(False)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["surface_alt"]))
            painter.drawRoundedRect(thumb, 6, 6)
            painter.setPen(QColor(tokens["muted"]))
            small = QFont(option.font)
            small.setPixelSize(10)
            painter.setFont(small)
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter, tr("memuat…"))

        name = str(index.data(int(Qt.ItemDataRole.DisplayRole)) or "")
        font = QFont(option.font)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(tokens["text"]))
        metrics = QFontMetrics(font)
        text_rect = QRectF(
            rect.left() + 3,
            thumb.bottom() + 5,
            rect.width() - 6,
            max(18, rect.bottom() - thumb.bottom() - 6),
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, int(text_rect.width())),
        )

        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens["focus"]), 1.5))
            painter.drawRoundedRect(rect, 8, 8)

        painter.restore()


class ResultsGallery(QWidget):
    openFolderRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._generation = 0
        self._results: list[FrameResult] = []
        self._elapsed_s = 0.0
        self._expected_total: int | None = None
        self._cancelled = False
        self._has_run = False
        self._signals = ThumbnailSignals(self)
        self._signals.ready.connect(self._on_thumbnail)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.title_label = QLabel()
        self.title_label.setObjectName("SectionTitle")
        header.addWidget(self.title_label)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("Muted")
        self.summary_label.setWordWrap(True)
        header.addWidget(self.summary_label, 1)
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self.openFolderRequested)
        header.addWidget(self.open_button)
        layout.addLayout(header)

        self.view = QListView()
        self.view.setObjectName("Gallery")
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setFlow(QListView.Flow.LeftToRight)
        self.view.setWrapping(True)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setUniformItemSizes(True)
        self.view.setIconSize(QSize(160, 90))
        self.view.setGridSize(GRID_SIZE)
        self.view.setSpacing(6)
        self.view.setWordWrap(False)
        self.view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAccessibleName("Galeri hasil ekstraksi")
        self.view.doubleClicked.connect(self._open_file)
        self.model = ResultsModel(self)
        self.view.setModel(self.model)
        self.view.setItemDelegate(ResultsDelegate(self.view))
        layout.addWidget(self.view, 1)

        self.empty_label = QLabel()
        self.empty_label.setObjectName("Muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        self.retranslate()

    def retranslate(self) -> None:
        self.title_label.setText(tr("Hasil"))
        self.open_button.setText(tr("Buka folder"))
        self.open_button.setToolTip(tr("Buka folder hasil di pengelola berkas"))
        self.open_button.setAccessibleName(tr("Buka folder hasil"))
        self.view.setAccessibleName(tr("Galeri hasil ekstraksi"))
        self.empty_label.setText(
            tr("Belum ada gambar. Jalankan ekstraksi untuk melihat hasil.")
        )
        self._render_summary()
        self.view.viewport().update()

    def _render_summary(self) -> None:
        total_size = sum(item.size_bytes for item in self._results)
        if not self._has_run:
            summary = tr("Belum ada hasil")
        elif self._cancelled:
            if self._expected_total:
                summary = tr(
                    "Dibatalkan · {n} dari {total} gambar tersimpan · {size}",
                    n=len(self._results),
                    total=format_count(self._expected_total),
                    size=human_bytes(total_size, language()),
                )
            else:
                summary = tr(
                    "Dibatalkan · {n} gambar tersimpan · {size}",
                    n=len(self._results),
                    size=human_bytes(total_size, language()),
                )
        elif self._results:
            summary = tr(
                "{n} gambar · {size} · {duration}",
                n=len(self._results),
                size=human_bytes(total_size, language()),
                duration=human_duration(self._elapsed_s, language()),
            )
        else:
            summary = tr("Tidak ada gambar yang dihasilkan")
        self.summary_label.setText(summary)

    def set_results(
        self,
        results: list[FrameResult],
        elapsed_s: float,
        *,
        expected_total: int | None = None,
        cancelled: bool = False,
    ) -> None:
        self._generation += 1
        generation = self._generation
        self._pool.clear()
        self._results = list(results)
        self._elapsed_s = elapsed_s
        self._expected_total = expected_total
        self._cancelled = cancelled
        self._has_run = True
        self.model.set_results(self._results)
        self.view.setVisible(bool(self._results))
        self.empty_label.setVisible(not self._results)
        self.open_button.setEnabled(bool(self._results))
        self.view.scrollToTop()
        self._render_summary()

        for row, result in enumerate(self._results):
            self._pool.start(
                ThumbnailTask(
                    row,
                    result.path,
                    generation,
                    self._signals,
                    THUMB_SIZE,
                )
            )

    def _on_thumbnail(self, generation: int, row: int, image: QImage) -> None:
        if generation == self._generation:
            self.model.set_thumbnail(row, image)

    def shutdown(self) -> None:
        """Hentikan pemuatan thumbnail sebelum jendela ditutup."""

        self._generation += 1
        self._pool.clear()
        self._pool.waitForDone(3000)

    def folder(self) -> Path | None:
        if self._results:
            return self._results[0].path.parent
        return None

    def _open_file(self, index) -> None:  # noqa: ANN001
        row = index.row()
        if 0 <= row < len(self._results):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._results[row].path)))
