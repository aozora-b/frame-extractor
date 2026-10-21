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

from ..i18n import tr, translate_message


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
        self._title = translate_message(title)
        self._message = translate_message(message)
        self._advice = translate_message(advice)
        self._detail = detail
        self._detail_visible = False
        self.setModal(True)
        self.setMinimumWidth(560)

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
        self.heading = QLabel()
        self.heading.setObjectName("BrandTitle")
        self.heading.setWordWrap(True)
        header.addWidget(self.heading, 1)
        layout.addLayout(header)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.body)

        self.advice_label = QLabel()
        self.advice_label.setObjectName("Muted")
        self.advice_label.setWordWrap(True)
        self.advice_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.advice_label.setVisible(bool(self._advice))
        layout.addWidget(self.advice_label)

        self.detail_edit = QTextEdit()
        self.detail_edit.setReadOnly(True)
        self.detail_edit.setPlainText(detail)
        self.detail_edit.setMinimumHeight(140)
        self.detail_edit.hide()

        self.detail_toggle = QToolButton()
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.setVisible(bool(detail))
        self.detail_toggle.toggled.connect(self._toggle_detail)
        layout.addWidget(self.detail_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.detail_edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.copy_button = QPushButton()
        self.copy_button.setVisible(bool(detail))
        self.copy_button.clicked.connect(self._copy)
        buttons.addWidget(self.copy_button)
        self.close_button = QPushButton()
        self.close_button.setObjectName("Primary")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(self._title)
        self.heading.setText(self._title)
        self.body.setText(self._message)
        self.advice_label.setText(tr("Saran: {advice}", advice=self._advice))
        self.detail_toggle.setText(
            tr("Sembunyikan detail teknis")
            if self._detail_visible
            else tr("Tampilkan detail teknis")
        )
        self.copy_button.setText(tr("Salin detail"))
        self.close_button.setText(tr("Tutup"))

    def _toggle_detail(self, checked: bool) -> None:
        self._detail_visible = checked
        self.detail_edit.setVisible(checked)
        self.detail_toggle.setText(
            tr("Sembunyikan detail teknis")
            if checked
            else tr("Tampilkan detail teknis")
        )
        if checked:
            self.adjustSize()

    def _copy(self) -> None:
        text = "\n\n".join(
            part
            for part in (
                self._title,
                self._message,
                tr("Saran: {advice}", advice=self._advice) if self._advice else "",
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
