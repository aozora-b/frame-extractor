"""Model Qt untuk antrean dan galeri hasil."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QRunnable, QSize, Qt, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap

from ..core.humanize import human_bytes
from ..core.models import FrameResult, VideoInfo
from ..core.naming import format_time


@dataclass
class QueueEntry:
    path: Path
    info: VideoInfo | None = None
    state: str = "waiting"
    detail: str = ""
    results: list[FrameResult] = field(default_factory=list)


class QueueModel(QAbstractListModel):
    PathRole = int(Qt.ItemDataRole.UserRole) + 1
    StateRole = int(Qt.ItemDataRole.UserRole) + 2
    DetailRole = int(Qt.ItemDataRole.UserRole) + 3

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[QueueEntry] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._entries)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._entries):
            return None
        entry = self._entries[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return entry.path.name
        if role == int(Qt.ItemDataRole.ToolTipRole):
            text = str(entry.path)
            if entry.info:
                text += (
                    f"\n{entry.info.width}×{entry.info.height} · "
                    f"{entry.info.fps:.2f} fps · {entry.info.codec}"
                )
            if entry.detail:
                text += f"\n{entry.detail}"
            return text
        if role == self.PathRole:
            return str(entry.path)
        if role == self.StateRole:
            return entry.state
        if role == self.DetailRole:
            return entry.detail
        return None

    def roleNames(self):  # noqa: N802
        return {
            self.PathRole: b"path",
            self.StateRole: b"state",
            self.DetailRole: b"detail",
        }

    def entries(self) -> list[QueueEntry]:
        return list(self._entries)

    def entry(self, row: int) -> QueueEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def row_for_path(self, path: Path) -> int:
        key = str(path.resolve()).casefold()
        for row, entry in enumerate(self._entries):
            if str(entry.path.resolve()).casefold() == key:
                return row
        return -1

    def add_paths(self, paths: list[Path]) -> list[int]:
        new_rows: list[int] = []
        existing = {str(entry.path.resolve()).casefold() for entry in self._entries}
        to_add: list[Path] = []
        for path in paths:
            key = str(path.resolve()).casefold()
            if key in existing:
                continue
            existing.add(key)
            to_add.append(path)

        if not to_add:
            return []

        start = len(self._entries)
        self.beginInsertRows(QModelIndex(), start, start + len(to_add) - 1)
        for path in to_add:
            self._entries.append(QueueEntry(path=path))
            new_rows.append(len(self._entries) - 1)
        self.endInsertRows()
        return new_rows

    def update_entry(
        self,
        path: Path,
        *,
        info: VideoInfo | None | object = ...,
        state: str | None = None,
        detail: str | None = None,
        results: list[FrameResult] | None = None,
    ) -> None:
        row = self.row_for_path(path)
        if row < 0:
            return
        entry = self._entries[row]
        if info is not ...:
            entry.info = info  # type: ignore[assignment]
        if state is not None:
            entry.state = state
        if detail is not None:
            entry.detail = detail
        if results is not None:
            entry.results = results
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [])

    def prepare_run(self) -> bool:
        """Siapkan antrean untuk batch baru tanpa mengulang item yang selesai.

        Item ``done`` dipertahankan agar tidak diekstrak ulang ketika pengguna
        menambahkan video lain. Item yang gagal atau dibatalkan dikembalikan ke
        ``waiting`` supaya tombol Mulai berfungsi sebagai coba-ulang.
        """

        retryable = {"error", "cancelled"}
        pending = False
        for entry in self._entries:
            if entry.state in retryable:
                entry.state = "waiting"
                entry.detail = ""
                entry.results = []
            if entry.state != "done":
                pending = True
        if self._entries:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._entries) - 1, 0), []
            )
        return pending

    def has_pending(self) -> bool:
        return any(entry.state != "done" for entry in self._entries)

    def remove_row(self, row: int) -> QueueEntry | None:
        if not 0 <= row < len(self._entries):
            return None
        self.beginRemoveRows(QModelIndex(), row, row)
        entry = self._entries.pop(row)
        self.endRemoveRows()
        return entry

    def clear(self) -> None:
        self.beginResetModel()
        self._entries.clear()
        self.endResetModel()


class ResultsModel(QAbstractListModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._results: list[FrameResult] = []
        self._thumbnails: dict[int, QPixmap] = {}

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._results)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._results):
            return None
        result = self._results[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return result.path.name
        if role == int(Qt.ItemDataRole.ToolTipRole):
            return (
                f"{result.path}\n"
                f"Waktu {format_time(result.timestamp_s)} · {human_bytes(result.size_bytes)}"
            )
        if role == int(Qt.ItemDataRole.DecorationRole):
            return self._thumbnails.get(index.row())
        if role == int(Qt.ItemDataRole.SizeHintRole):
            # Harus tetap sama meski thumbnail belum termuat; bila tidak, Qt
            # mengunci tinggi item ke tinggi teks dan gambar terpotong.
            return QSize(184, 148)
        if role == int(Qt.ItemDataRole.UserRole):
            return str(result.path)
        return None

    def results(self) -> list[FrameResult]:
        return list(self._results)

    def thumbnail_count(self) -> int:
        return len(self._thumbnails)

    def set_results(self, results: list[FrameResult]) -> None:
        self.beginResetModel()
        self._results = list(results)
        self._thumbnails.clear()
        self.endResetModel()

    def set_thumbnail(self, row: int, image: QImage) -> None:
        if not 0 <= row < len(self._results):
            return
        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return
        self._thumbnails[row] = pixmap
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [int(Qt.ItemDataRole.DecorationRole)])

    def clear(self) -> None:
        self.set_results([])


class ThumbnailSignals(QObject):
    ready = Signal(int, int, QImage)


class ThumbnailTask(QRunnable):
    """Membaca thumbnail di thread pool agar UI tidak tersendat."""

    def __init__(
        self,
        row: int,
        path: Path,
        generation: int,
        signals: ThumbnailSignals,
        size: QSize,
    ) -> None:
        super().__init__()
        self.row = row
        self.path = path
        self.generation = generation
        self.signals = signals
        self.size = size
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401
        reader = QImageReader(str(self.path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid() and not source_size.isEmpty():
            scaled = source_size.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(scaled)
        image = reader.read()
        if not image.isNull():
            self.signals.ready.emit(self.generation, self.row, image)
