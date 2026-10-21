"""Zona jatuh berkas dengan dukungan drag-and-drop dan keyboard."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr


class _FilmIcon(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(88, 88)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = self.palette().color(QPalette.ColorRole.Highlight)
        soft = QColor(accent)
        soft.setAlpha(30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(soft)
        painter.drawEllipse(QRectF(2, 2, 84, 84))

        pen = QPen(accent, 3.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        body = QRectF(17, 24, 54, 32)
        painter.drawRoundedRect(body, 5, 5)

        hole_brush = QColor(accent)
        painter.setBrush(hole_brush)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(4):
            x = body.left() + 6 + index * 12.4
            painter.drawRoundedRect(QRectF(x, 28, 4.5, 4), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(x, 48, 4.5, 4), 1.2, 1.2)

        painter.setPen(QPen(accent, 3.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(44, 57), QPointF(44, 68))
        painter.drawLine(QPointF(38, 63), QPointF(44, 69))
        painter.drawLine(QPointF(50, 63), QPointF(44, 69))


class DropZone(QFrame):
    browseFiles = Signal()
    browseFolder = Signal()
    pathsDropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 48, 40, 48)
        layout.setSpacing(10)
        layout.addStretch(1)

        icon = _FilmIcon(self)
        icon_row = QHBoxLayout()
        icon_row.addStretch(1)
        icon_row.addWidget(icon)
        icon_row.addStretch(1)
        layout.addLayout(icon_row)

        self.title_label = QLabel()
        self.title_label.setObjectName("BrandTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("Muted")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        self.formats_label = QLabel()
        self.formats_label.setObjectName("StatCaption")
        self.formats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formats_label.setWordWrap(True)
        layout.addWidget(self.formats_label)

        layout.addSpacing(10)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        self.choose_button = QPushButton()
        self.choose_button.setObjectName("Primary")
        self.choose_button.setMinimumWidth(150)
        self.choose_button.clicked.connect(self.browseFiles)
        buttons.addWidget(self.choose_button)

        self.folder_button = QPushButton()
        self.folder_button.setMinimumWidth(130)
        self.folder_button.clicked.connect(self.browseFolder)
        buttons.addWidget(self.folder_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        self.setAccessibleName(tr("Zona jatuh berkas video"))
        self.setAccessibleDescription(
            tr(
                "Jatuhkan berkas video atau folder ke sini, atau tekan Enter untuk memilih berkas."
            )
        )
        self.title_label.setText(tr("Jatuhkan video atau folder di sini"))
        self.subtitle_label.setText(
            tr("atau klik area ini untuk memilih berkas dari komputer")
        )
        self.formats_label.setText(
            tr("MP4 · MKV · MOV · WebM · AVI · MPEG · MTS · dan lainnya")
        )
        self.choose_button.setText(tr("Pilih video"))
        self.choose_button.setToolTip(tr("Buka dialog pemilih berkas (Ctrl+O)"))
        self.choose_button.setAccessibleName(tr("Pilih video"))
        self.folder_button.setText(tr("Pilih folder"))
        self.folder_button.setToolTip(
            tr("Tambahkan semua video di dalam sebuah folder")
        )
        self.folder_button.setAccessibleName(tr("Pilih folder"))

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def dragEnterEvent(self, event) -> None:  # noqa: ANN001, N802
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001, N802
        self._set_drag_active(False)
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile()
        ]
        if paths:
            event.acceptProposedAction()
            self.pathsDropped.emit(paths)
        else:
            event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.browseFiles.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.browseFiles.emit()
            event.accept()
            return
        super().keyPressEvent(event)
