"""Kartu informasi video."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ...core.humanize import human_duration
from ...core.models import VideoInfo


class _Stat(QWidget):
    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.value = QLabel("—")
        self.value.setObjectName("StatValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption = QLabel(caption)
        self.caption.setObjectName("StatCaption")
        layout.addWidget(self.value)
        layout.addWidget(self.caption)
        self.setAccessibleName(caption)


class VideoInfoCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        eyebrow = QLabel("VIDEO")
        eyebrow.setObjectName("StatCaption")
        layout.addWidget(eyebrow)

        self.name_label = QLabel("Belum ada video")
        self.name_label.setObjectName("BrandTitle")
        self.name_label.setWordWrap(True)
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.name_label)

        stats = QGridLayout()
        stats.setHorizontalSpacing(28)
        stats.setVerticalSpacing(8)
        self.duration = _Stat("durasi")
        self.fps = _Stat("frame/detik")
        self.resolution = _Stat("resolusi")
        self.frames = _Stat("total frame")
        self.codec = _Stat("codec")
        widgets = [self.duration, self.fps, self.resolution, self.frames, self.codec]
        for column, widget in enumerate(widgets):
            stats.addWidget(widget, 0, column)
            stats.setColumnStretch(column, 1)
        layout.addLayout(stats)

        self.warning = QLabel()
        self.warning.setObjectName("Warning")
        self.warning.setWordWrap(True)
        self.warning.hide()
        layout.addWidget(self.warning)

    def set_info(self, info: VideoInfo | None) -> None:
        if info is None:
            self.name_label.setText("Belum ada video")
            for stat in (
                self.duration,
                self.fps,
                self.resolution,
                self.frames,
                self.codec,
            ):
                stat.value.setText("—")
            self.warning.hide()
            self.setToolTip("")
            return

        self.name_label.setText(info.path.name)
        self.name_label.setToolTip(str(info.path))
        self.setToolTip(str(info.path))
        self.duration.value.setText(human_duration(info.duration_s))
        self.fps.value.setText(f"{info.fps:.2f}")
        self.resolution.value.setText(f"{info.width}×{info.height}")
        self.frames.value.setText(f"{info.frame_count:,}".replace(",", "."))
        self.codec.value.setText(info.codec.upper())
        if info.warnings:
            self.warning.setText("\n".join(info.warnings))
            self.warning.show()
        else:
            self.warning.hide()
