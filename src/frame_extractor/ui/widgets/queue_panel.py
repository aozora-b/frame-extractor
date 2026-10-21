"""Panel antrean batch dengan status per baris."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..models import QueueModel
from ..theme import PALETTES

STATE_LABELS = {
    "waiting": "Menunggu",
    "probing": "Membaca metadata…",
    "ready": "Siap",
    "running": "Memproses…",
    "done": "Selesai",
    "error": "Gagal",
    "cancelled": "Dibatalkan",
}

STATE_COLORS = {
    "waiting": "muted",
    "probing": "muted",
    "ready": "accent",
    "running": "accent",
    "done": "success",
    "error": "danger",
    "cancelled": "warning",
}


def current_tokens() -> dict[str, str]:
    app = QApplication.instance()
    name = app.property("themeName") if app else "dark"
    return PALETTES["light" if name == "light" else "dark"]


class QueueDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(240, 62)

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        tokens = current_tokens()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            color = QColor(tokens["selection"])
            color.setAlpha(150)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 8, 8)
        elif hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["surface_alt"]))
            painter.drawRoundedRect(rect, 8, 8)

        row = index.row()
        state = index.data(QueueModel.StateRole) or "waiting"
        detail = index.data(QueueModel.DetailRole) or ""
        name = index.data(int(Qt.ItemDataRole.DisplayRole)) or ""
        path = index.data(QueueModel.PathRole) or ""

        # Badge nomor.
        badge = QRectF(rect.left() + 10, rect.center().y() - 12, 24, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        badge_color = QColor(tokens["surface_alt"])
        if selected:
            badge_color = QColor(tokens["elevated"])
        painter.setBrush(badge_color)
        painter.drawEllipse(badge)
        badge_font = QFont(option.font)
        badge_font.setPixelSize(11)
        badge_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(badge_font)
        painter.setPen(QColor(tokens["muted"]))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(row + 1))

        text_left = rect.left() + 44
        status = tr(STATE_LABELS.get(state, state))
        status_color = QColor(tokens[STATE_COLORS.get(state, "muted")])
        status_font = QFont(option.font)
        status_font.setPixelSize(11)
        status_font.setWeight(QFont.Weight.DemiBold)
        status_metrics = QFontMetrics(status_font)
        status_width = status_metrics.horizontalAdvance(status)

        name_font = QFont(option.font)
        name_font.setPixelSize(13)
        name_font.setWeight(QFont.Weight.Medium)
        name_metrics = QFontMetrics(name_font)
        available = rect.width() - 54 - status_width - 16
        elided_name = name_metrics.elidedText(str(name), Qt.TextElideMode.ElideMiddle, max(40, available))

        painter.setFont(name_font)
        painter.setPen(QColor(tokens["text"]))
        painter.drawText(
            QRectF(text_left, rect.top() + 8, max(40, available), 20),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided_name,
        )

        painter.setFont(status_font)
        painter.setPen(status_color)
        painter.drawText(
            QRectF(rect.right() - status_width - 10, rect.top() + 8, status_width, 20),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            status,
        )

        second = detail or str(Path(path).parent)
        second_font = QFont(option.font)
        second_font.setPixelSize(11)
        second_metrics = QFontMetrics(second_font)
        elided_second = second_metrics.elidedText(
            str(second).replace("\\", "/"), Qt.TextElideMode.ElideMiddle, int(rect.width() - 56)
        )
        painter.setFont(second_font)
        painter.setPen(QColor(tokens["muted"] if state not in ("error", "cancelled") else status_color.name()))
        painter.drawText(
            QRectF(text_left, rect.top() + 30, rect.width() - 54, 18),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided_second,
        )

        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(tokens["focus"]), 1.5))
            painter.drawRoundedRect(rect, 8, 8)

        painter.restore()


class QueuePanel(QFrame):
    addRequested = Signal()
    removeRequested = Signal(object)
    currentPathChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._running = False
        self.model = QueueModel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setObjectName("SectionTitle")
        header.addWidget(self.title_label)
        self.count_label = QLabel()
        self.count_label.setObjectName("Muted")
        header.addWidget(self.count_label)
        header.addStretch(1)
        self.add_button = QPushButton()
        self.add_button.clicked.connect(self.addRequested)
        header.addWidget(self.add_button)
        self.remove_button = QPushButton()
        self.remove_button.setObjectName("Danger")
        self.remove_button.clicked.connect(self._request_remove)
        header.addWidget(self.remove_button)
        layout.addLayout(header)

        self.view = QListView()
        self.view.setObjectName("Queue")
        self.view.setModel(self.model)
        self.view.setItemDelegate(QueueDelegate(self.view))
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setMinimumHeight(130)
        self.view.setSpacing(0)
        self.view.setAccessibleName("Antrean video")
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.view, 1)

        self.remove_action = QAction("Hapus dari antrean", self)
        self.remove_action.setShortcut(QKeySequence("Delete"))
        self.remove_action.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.remove_action.triggered.connect(self._request_remove)
        self.view.addAction(self.remove_action)

        self.model.rowsInserted.connect(self._update_count)
        self.model.rowsRemoved.connect(self._update_count)
        self.model.modelReset.connect(self._update_count)
        self.view.selectionModel().currentChanged.connect(self._on_current_changed)
        self.retranslate()

    def retranslate(self) -> None:
        self.title_label.setText(tr("Antrean"))
        self.add_button.setText(tr("Tambah video"))
        self.add_button.setToolTip(
            tr("Tambahkan video lain ke antrean (Ctrl+Shift+O)")
        )
        self.add_button.setAccessibleName(tr("Tambah video"))
        self.remove_button.setText(tr("Hapus"))
        self.remove_button.setToolTip(
            tr("Hapus video terpilih dari antrean (Delete)")
        )
        self.remove_button.setAccessibleName(tr("Hapus video dari antrean"))
        self.view.setAccessibleName(tr("Antrean video"))
        self.remove_action.setText(tr("Hapus dari antrean"))
        self._update_count()
        self.view.viewport().update()

    def _update_count(self, *args) -> None:  # noqa: ANN002
        count = self.model.rowCount()
        self.count_label.setText(tr("{n} video", n=count))
        self.add_button.setEnabled(count > 0 and not self._running)
        self._update_remove_enabled()

    def _update_remove_enabled(self) -> None:
        enabled = not self._running and self.current_path() is not None
        self.remove_button.setEnabled(enabled)
        self.remove_action.setEnabled(enabled)

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:  # noqa: ARG002
        self._update_remove_enabled()
        if current.isValid():
            entry = self.model.entry(current.row())
            if entry is not None:
                self.currentPathChanged.emit(entry.path)

    def _request_remove(self) -> None:
        path = self.current_path()
        if path is not None and not self._running:
            self.removeRequested.emit(path)

    def _show_context_menu(self, pos) -> None:  # noqa: ANN001
        index = self.view.indexAt(pos)
        if not index.isValid() or self._running:
            return
        self.view.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction(self.remove_action)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def set_running(self, running: bool) -> None:
        self._running = running
        self.view.setEnabled(not running)
        self.add_button.setEnabled(not running and self.model.rowCount() > 0)
        self._update_remove_enabled()

    def select_path(self, path: Path) -> None:
        row = self.model.row_for_path(path)
        if row >= 0:
            self.view.setCurrentIndex(self.model.index(row, 0))
            self.view.scrollTo(self.model.index(row, 0))

    def current_path(self) -> Path | None:
        index = self.view.currentIndex()
        if not index.isValid():
            return None
        entry = self.model.entry(index.row())
        return entry.path if entry else None
