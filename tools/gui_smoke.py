"""Uji asap GUI tanpa layar: muat video, ekstrak, lalu periksa galeri.

Dipakai oleh ``pytest -m gui`` dan dapat dijalankan manual:

    python tools/gui_smoke.py --video sample.mp4 --out hasil
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frame_extractor import APP_NAME, ORG_NAME  # noqa: E402
from frame_extractor.ui.main_window import MainWindow  # noqa: E402


def _wait(app: QApplication, predicate, timeout_s: float) -> bool:  # noqa: ANN001
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    app.processEvents()
    return bool(predicate())


def run(video: Path, out_dir: Path) -> tuple[int, int]:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")

    with tempfile.TemporaryDirectory(prefix="frame-extractor-gui-") as tmp:
        settings = QSettings(
            str(Path(tmp) / "settings.ini"), QSettings.Format.IniFormat
        )
        window = MainWindow(settings)
        window.show()
        window.add_paths([video])

        def probed() -> bool:
            entry = window.queue_panel.model.entry(0)
            return entry is not None and entry.info is not None

        if not _wait(app, probed, 30):
            window.close()
            raise RuntimeError("Metadata video tidak terbaca di GUI.")

        window.settings_panel.out_edit.setText(str(out_dir))
        window.settings_panel.interval_spin.setValue(1.0)
        window._recalc_estimate()
        window._start_batch()

        if not _wait(app, lambda: not window._running, 180):
            window._request_cancel()
            _wait(app, lambda: not window._running, 10)
            window.close()
            raise RuntimeError("Ekstraksi GUI tidak selesai dalam batas waktu.")

        rows = window.gallery.model.rowCount()
        errors = list(window._batch_errors)
        window.close()
        app.processEvents()

    if errors:
        raise RuntimeError(f"Ekstraksi melaporkan galat: {errors[0][1]}")
    if rows == 0:
        raise RuntimeError("Galeri kosong setelah ekstraksi.")
    files = list(out_dir.glob("*.png"))
    if not files:
        raise RuntimeError("Tidak ada berkas PNG di folder keluaran.")
    return rows, len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Uji asap GUI Frame Extractor.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rows, files = run(args.video, args.out)
    except Exception as exc:  # noqa: BLE001
        print(f"Uji asap GUI gagal: {exc}", file=sys.stderr)
        return 1
    print(f"Uji asap GUI lulus: {rows} item di galeri, {files} berkas di folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
