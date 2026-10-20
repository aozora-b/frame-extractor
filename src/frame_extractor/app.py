"""Titik masuk aplikasi GUI Frame Extractor."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import logging
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, ORG_NAME, __version__
from .core.extract import extract
from .core.models import ExtractOptions
from .core.probe import probe
from .logging_setup import configure_logging, get_log_path
from .ui.main_window import MainWindow
from .ui.theme import app_icon

log = logging.getLogger(__name__)

_APP_USER_MODEL_ID = "FrameExtractor.FrameExtractor.1"


def _set_windows_app_id() -> None:
    """Beri Windows identitas aplikasi agar ikon taskbar tidak memakai ikon Python."""

    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            _APP_USER_MODEL_ID
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="frame-extractor",
        description="Ekstrak frame dari video menjadi PNG atau JPG dengan antarmuka grafis.",
    )
    parser.add_argument(
        "videos",
        metavar="VIDEO",
        nargs="*",
        type=Path,
        help="satu atau beberapa video yang langsung dibuka saat aplikasi mulai",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="buka jendela sebentar lalu keluar (untuk menguji hasil build)",
    )
    parser.add_argument(
        "--self-test",
        metavar="VIDEO",
        type=Path,
        help="uji mesin ekstraksi tanpa membuka jendela, lalu keluar",
    )
    parser.add_argument(
        "--out",
        metavar="FOLDER",
        type=Path,
        help="folder keluaran untuk --self-test",
    )
    return parser


def _self_test(video: Path, out_dir: Path | None) -> int:
    """Uji mandiri mesin ekstraksi; dipakai smoke test hasil packaging."""

    with tempfile.TemporaryDirectory(prefix="frame-extractor-self-test-") as temp:
        destination = out_dir or Path(temp)
        destination.mkdir(parents=True, exist_ok=True)
        try:
            info = probe(video)
            results = extract(
                info,
                ExtractOptions(mode="count", frame_total=3, out_dir=destination),
            )
        except Exception:
            log.exception("Uji mandiri gagal untuk %s", video)
            return 1
        if not results or not all(result.path.is_file() for result in results):
            log.error("Uji mandiri tidak menghasilkan berkas gambar.")
            return 1
        log.info(
            "Uji mandiri lulus: %d gambar dari %s (%dx%d, %s)",
            len(results),
            video.name,
            info.width,
            info.height,
            info.codec,
        )
        return 0


def _install_exception_hook(*, show_dialog: bool = True) -> None:
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger(__name__).critical(
            "Kesalahan tak tertangani", exc_info=(exc_type, exc_value, exc_traceback)
        )
        app = QApplication.instance()
        if app is None or not show_dialog:
            previous(exc_type, exc_value, exc_traceback)
            return
        QMessageBox.critical(
            None,
            "Kesalahan tak terduga",
            "Aplikasi mengalami kesalahan yang tidak terduga.\n\n"
            f"Detail lengkap tercatat di log:\n{get_log_path()}\n\n"
            "Anda dapat melanjutkan, tetapi sebaiknya simpan pekerjaan dan "
            "jalankan ulang aplikasi.",
        )

    sys.excepthook = hook


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _set_windows_app_id()

    if args.self_test is not None:
        configure_logging()
        return _self_test(args.self_test, args.out)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    with contextlib.suppress(AttributeError):
        app.setDesktopFileName("frame-extractor")

    configure_logging()
    _install_exception_hook(show_dialog=not args.smoke_test)
    log.info("Frame Extractor %s dimulai", __version__)

    settings = QSettings(ORG_NAME, APP_NAME)
    try:
        window = MainWindow(settings)
    except Exception:
        log.exception("Jendela utama gagal dibuat")
        if not args.smoke_test:
            QMessageBox.critical(
                None,
                "Aplikasi gagal dimulai",
                "Jendela utama tidak dapat dibuka.\n\n"
                f"Detail lengkap tercatat di log:\n{get_log_path()}",
            )
        return 1
    window.show()

    videos = [path for path in args.videos if path]
    if videos:
        QTimer.singleShot(0, lambda: window.add_paths(videos))

    if args.smoke_test:
        QTimer.singleShot(1200, app.quit)

    code = app.exec()
    log.info("Frame Extractor berhenti dengan kode %s", code)
    return int(code)


__all__ = ["main", "build_parser"]
