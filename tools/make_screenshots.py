"""Buat tangkapan layar dan GIF demo dari GUI yang benar-benar berjalan."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frame_extractor import APP_NAME, ORG_NAME  # noqa: E402
from frame_extractor.ui.main_window import MainWindow  # noqa: E402
from tools.make_test_video import make_test_video  # noqa: E402


def _wait(app: QApplication, predicate, timeout_s: float) -> bool:  # noqa: ANN001
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(predicate())


def _grab(window: MainWindow, path: Path) -> None:
    window.repaint()
    QApplication.processEvents()
    pixmap = window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Gagal menyimpan tangkapan layar: {path}")


def _make_gif(frames: list[Path], destination: Path) -> None:
    from PIL import Image

    images = []
    for frame in frames:
        image = Image.open(frame).convert("RGB")
        image.thumbnail((1000, 700), Image.Resampling.LANCZOS)
        images.append(image)
    if not images:
        return
    width, height = images[0].size
    normalized = []
    for image in images:
        canvas = Image.new("RGB", (width, height), "#14161a")
        canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
        normalized.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
    normalized[0].save(
        destination,
        save_all=True,
        append_images=normalized[1:],
        duration=[1800, 900, 2600],
        loop=0,
        optimize=True,
    )


def run(video: Path | None, assets: Path) -> None:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")

    temp_root = Path(tempfile.mkdtemp(prefix="frame-extractor-shots-"))
    if video is None:
        video = make_test_video(
            temp_root / "demo.mp4", seconds=10, fps=30, width=1280, height=720
        )
    out_dir = temp_root / "hasil"
    frames: list[Path] = []

    settings = QSettings(str(temp_root / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings)
    window.resize(1180, 800)
    window.show()
    app.processEvents()

    window.add_paths([video])

    def probed() -> bool:
        entry = window.queue_panel.model.entry(0)
        return entry is not None and entry.info is not None

    if not _wait(app, probed, 45):
        window.close()
        raise RuntimeError("Metadata video demo tidak terbaca.")

    window.settings_panel.interval_spin.setValue(0.5)
    window.settings_panel.out_edit.setText(str(out_dir))
    window._recalc_estimate()
    app.processEvents()

    main_shot = assets / "screenshot-main.png"
    _grab(window, main_shot)
    frames.append(main_shot)

    window._start_batch()
    progress_shot = temp_root / "progress.png"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and window._running:
        app.processEvents()
        if window._current_done >= 5 and not progress_shot.exists():
            _grab(window, progress_shot)
            frames.append(progress_shot)
        time.sleep(0.01)
    app.processEvents()

    if window._running:
        window._request_cancel()
        _wait(app, lambda: not window._running, 10)
        window.close()
        raise RuntimeError("Ekstraksi demo tidak selesai.")

    if not progress_shot.exists():
        progress_shot = temp_root / "progress.png"
        _grab(window, progress_shot)
        frames.append(progress_shot)

    target_thumbnails = min(6, window.gallery.model.rowCount())
    _wait(
        app,
        lambda: window.gallery.model.thumbnail_count() >= target_thumbnails,
        15,
    )
    results_shot = assets / "screenshot-results.png"
    _grab(window, results_shot)
    frames.append(results_shot)

    window.close()
    app.processEvents()

    _make_gif(frames, assets / "demo.gif")
    print(f"Tangkapan layar: {main_shot}")
    print(f"Tangkapan layar: {results_shot}")
    print(f"GIF: {assets / 'demo.gif'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buat tangkapan layar GUI.")
    parser.add_argument("--video", type=Path, default=None)
    parser.add_argument("--assets", type=Path, default=ROOT / "assets")
    args = parser.parse_args(argv)
    try:
        run(args.video, args.assets)
    except Exception as exc:  # noqa: BLE001
        print(f"Gagal membuat tangkapan layar: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
