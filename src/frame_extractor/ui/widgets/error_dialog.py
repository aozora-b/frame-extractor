"""Dialog galat yang bisa ditindaklanjuti, dengan detail teknis yang dapat disalin."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ErrorDialog(QDialog):
    def __init__(
        self,
        title: str,
        message: str,
        advice: str = "",
        detail: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(560)
        self._title = title
        self._message = message
        self._advice = advice
        self._detail = detail

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            .pixmap(40, 40)
        )
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        heading = QLabel(title)
        heading.setObjectName("BrandTitle")
        heading.setWordWrap(True)
        header.addWidget(heading, 1)
        layout.addLayout(header)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        if advice:
            advice_label = QLabel(f"Saran: {advice}")
            advice_label.setObjectName("Muted")
            advice_label.setWordWrap(True)
            advice_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(advice_label)

        self.detail_edit = QTextEdit()
        self.detail_edit.setReadOnly(True)
        self.detail_edit.setPlainText(detail)
        self.detail_edit.setMinimumHeight(140)
        self.detail_edit.hide()

        self.detail_toggle = QToolButton()
        self.detail_toggle.setText("Tampilkan detail teknis")
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.setVisible(bool(detail))
        self.detail_toggle.toggled.connect(self._toggle_detail)
        layout.addWidget(self.detail_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.detail_edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.copy_button = QPushButton("Salin detail")
        self.copy_button.setVisible(bool(detail))
        self.copy_button.clicked.connect(self._copy)
        buttons.addWidget(self.copy_button)
        close_button = QPushButton("Tutup")
        close_button.setObjectName("Primary")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _toggle_detail(self, checked: bool) -> None:
        self.detail_edit.setVisible(checked)
        self.detail_toggle.setText(
            "Sembunyikan detail teknis" if checked else "Tampilkan detail teknis"
        )
        if checked:
            self.adjustSize()

    def _copy(self) -> None:
        text = "\n\n".join(
            part
            for part in (
                self._title,
                self._message,
                f"Saran: {self._advice}" if self._advice else "",
                self._detail,
            )
            if part
        )
        QApplication.clipboard().setText(text)


def show_error(
    parent: QWidget | None,
    title: str,
    message: str,
    advice: str = "",
    detail: str = "",
) -> None:
    dialog = ErrorDialog(title, message, advice, detail, parent)
    dialog.exec()
