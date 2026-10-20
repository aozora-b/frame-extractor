"""Konfigurasi logging ke berkas dan detail lokasi log."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH: Path | None = None
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def get_log_path() -> Path:
    return LOG_PATH or Path("frame-extractor.log")


def configure_logging(log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Pasang handler berkas (rotasi 1 MB × 3) dan kembalikan path log."""

    global LOG_PATH
    if log_dir is None:
        from PySide6.QtCore import QStandardPaths

        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        log_dir = Path(base) / "logs" if base else Path.home() / ".frame-extractor" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "frame-extractor.log"
    LOG_PATH = log_path

    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_048_576, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    if sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        stream.setLevel(logging.WARNING)
        root.addHandler(stream)

    logging.getLogger(__name__).info("Log dimulai: %s", log_path)
    return log_path
