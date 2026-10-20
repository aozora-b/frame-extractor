"""Worker Qt untuk probe dan ekstraksi. Tidak pernah menyentuh widget dari thread lain."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .core.errors import DomainError
from .core.extract import Engine, extract
from .core.models import ExtractOptions, FrameResult, VideoInfo
from .core.probe import probe
from .logging_setup import get_log_path

log = logging.getLogger(__name__)


def describe_exception(exc: BaseException) -> str:
    if isinstance(exc, DomainError):
        parts = [exc.message]
        if exc.advice:
            parts.append(f"Saran: {exc.advice}")
        if exc.detail:
            parts.append(f"Detail teknis:\n{exc.detail}")
        return "\n\n".join(parts)
    return (
        f"{type(exc).__name__}: {exc}\n\n"
        f"Detail lengkap tercatat di log:\n{get_log_path()}"
    )


class ProbeWorker(QObject):
    """Membaca metadata satu video di thread terpisah."""

    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    @Slot()
    def run(self) -> None:
        try:
            info = probe(self.path)
        except DomainError as exc:
            log.warning("Probe gagal untuk %s: %s", self.path, exc)
            self.failed.emit(exc.title, describe_exception(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("Probe tak terduga untuk %s", self.path)
            self.failed.emit("Metadata tidak terbaca", describe_exception(exc))
        else:
            self.finished.emit(info)


class ExtractWorker(QObject):
    """Menjalankan ekstraksi di QThread; pembatalan lewat Event (thread-safe)."""

    progress = Signal(int, int, float)
    stage = Signal(str)
    finished = Signal(list)
    failed = Signal(str, str)
    cancelled = Signal(int)

    def __init__(
        self,
        info: VideoInfo,
        options: ExtractOptions,
        engine: Engine = "auto",
    ) -> None:
        super().__init__()
        self.info = info
        self.options = options
        self.engine = engine
        self._cancel_event = threading.Event()
        self._total = 0
        self.last_results: list[FrameResult] = []

    def request_cancel(self) -> None:
        """Dipanggil langsung dari thread UI; hanya menyentuh Event."""

        self._cancel_event.set()

    @property
    def is_cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def _on_progress(self, done: int, total: int, ts: float) -> None:
        self._total = total
        self.progress.emit(done, total, ts)

    @Slot()
    def run(self) -> None:
        self.stage.emit("memeriksa")
        try:
            self.stage.emit("mengekstrak")
            results = extract(
                self.info,
                self.options,
                on_progress=self._on_progress,
                should_cancel=self._cancel_event.is_set,
                engine=self.engine,
            )
        except DomainError as exc:
            partial = getattr(exc, "partial_results", None)
            if partial:
                self.last_results = list(partial)
            log.error("Ekstraksi gagal untuk %s: %s", self.info.path, exc)
            self.failed.emit(exc.title, describe_exception(exc))
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("Ekstraksi tak terduga untuk %s", self.info.path)
            self.failed.emit("Kesalahan tak terduga", describe_exception(exc))
            return

        self.last_results = list(results)
        if self._cancel_event.is_set() and self._total and len(results) < self._total:
            log.info("Ekstraksi dibatalkan pada %d/%d frame", len(results), self._total)
            self.cancelled.emit(len(results))
            return
        self.finished.emit(list(results))
