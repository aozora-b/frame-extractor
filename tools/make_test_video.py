"""Pembuat video uji sintetis yang deterministik.

Video berdurasi 10 detik, 10 fps, dengan angka besar per detik dan warna latar
yang berbeda tiap detik. Warna diambil dari ``SECOND_COLORS`` agar tes bisa
memverifikasi isi piksel frame tertentu tanpa OCR.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Warna BGR (urutan OpenCV), satu warna per detik.
SECOND_COLORS: tuple[tuple[int, int, int], ...] = (
    (32, 32, 32),
    (48, 48, 190),
    (50, 150, 60),
    (180, 90, 40),
    (120, 60, 180),
    (40, 170, 200),
    (190, 190, 50),
    (60, 100, 220),
    (170, 60, 140),
    (80, 170, 170),
)


def make_test_video(
    path: Path,
    seconds: int = 10,
    fps: int = 10,
    width: int = 320,
    height: int = 240,
) -> Path:
    """Buat video uji. Mengembalikan path yang ditulis."""

    import cv2
    import numpy as np

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV tidak dapat membuat video uji (codec mp4v tidak tersedia).")

    total_frames = max(1, seconds * fps)
    try:
        for frame_number in range(total_frames):
            second = frame_number // fps
            color = SECOND_COLORS[second % len(SECOND_COLORS)]
            frame = np.full((height, width, 3), color, dtype=np.uint8)

            # Angka detik besar di tengah.
            label = str(second)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 4.2 if len(label) == 1 else 3.2
            thickness = 9
            (text_width, text_height), baseline = cv2.getTextSize(
                label, font, scale, thickness
            )
            origin = (
                (width - text_width) // 2,
                (height + text_height) // 2 - baseline // 2,
            )
            cv2.putText(
                frame,
                label,
                origin,
                font,
                scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

            # Penanda gerak: balok yang bergeser di bagian bawah.
            bar_width = max(12, width // 12)
            bar_x = int(frame_number % max(1, width - bar_width))
            cv2.rectangle(
                frame,
                (bar_x, height - 24),
                (bar_x + bar_width, height - 12),
                (0, 255, 255),
                -1,
            )

            # Teks kecil agar frame mudah dikenali secara visual.
            cv2.putText(
                frame,
                "FRAME EXTRACTOR TEST",
                (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (235, 235, 235),
                1,
                cv2.LINE_AA,
            )

            # Kotak warna murni di kiri atas untuk verifikasi piksel.
            frame[5:30, 5:30] = color

            writer.write(frame)
    finally:
        writer.release()

    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Video uji gagal dibuat.")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buat video uji sintetis 10 detik.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args(argv)
    result = make_test_video(
        args.output,
        seconds=args.seconds,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    print(f"Video uji dibuat: {result} ({result.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
