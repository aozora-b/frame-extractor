from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PACKAGE_ASSETS = ROOT / "src" / "frame_extractor" / "assets"


def rounded_gradient(size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = base.load()
    top = (16, 34, 56)
    bottom = (9, 20, 34)
    for y in range(size):
        mix = y / max(1, size - 1)
        color = tuple(int(top[i] * (1 - mix) + bottom[i] * mix) for i in range(3)) + (255,)
        for x in range(size):
            pixels[x, y] = color
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=255)
    base.putalpha(mask)
    return base


def draw_icon(size: int = 1024) -> Image.Image:
    image = rounded_gradient(size)
    draw = ImageDraw.Draw(image)
    s = size

    # Bingkai film dengan perforasi.
    left, top, right, bottom = int(s * 0.16), int(s * 0.20), int(s * 0.84), int(s * 0.68)
    radius = int(s * 0.055)
    draw.rounded_rectangle((left, top, right, bottom), radius=radius, outline=(90, 169, 255), width=int(s * 0.035))
    hole_w, hole_h = int(s * 0.045), int(s * 0.038)
    for i in range(4):
        x = left + int((right - left) * (0.12 + i * 0.255)) - hole_w // 2
        draw.rounded_rectangle((x, top + int(s * 0.035), x + hole_w, top + int(s * 0.035) + hole_h), radius=int(s * 0.008), fill=(144, 201, 255))
        draw.rounded_rectangle((x, bottom - int(s * 0.035) - hole_h, x + hole_w, bottom - int(s * 0.035)), radius=int(s * 0.008), fill=(144, 201, 255))

    # Tiga bingkai kecil di dalam film.
    frame_w = int((right - left) * 0.24)
    frame_h = int((bottom - top) * 0.42)
    frame_top = top + int((bottom - top) * 0.30)
    for i in range(3):
        x = left + int((right - left) * (0.10 + i * 0.31))
        draw.rounded_rectangle((x, frame_top, x + frame_w, frame_top + frame_h), radius=int(s * 0.012), fill=(232, 244, 255))

    # Panah ekstraksi ke bawah.
    cx = s // 2
    arrow_top = int(s * 0.51)
    arrow_bottom = int(s * 0.82)
    shaft_w = int(s * 0.075)
    draw.rounded_rectangle((cx - shaft_w // 2, arrow_top, cx + shaft_w // 2, arrow_bottom - int(s * 0.10)), radius=int(s * 0.015), fill=(90, 169, 255))
    draw.polygon(
        [
            (cx - int(s * 0.15), arrow_bottom - int(s * 0.16)),
            (cx + int(s * 0.15), arrow_bottom - int(s * 0.16)),
            (cx, arrow_bottom),
        ],
        fill=(90, 169, 255),
    )

    # Baki/tray di bawah.
    tray_y = int(s * 0.855)
    draw.rounded_rectangle(
        (int(s * 0.26), tray_y, int(s * 0.74), tray_y + int(s * 0.055)),
        radius=int(s * 0.012),
        fill=(232, 244, 255),
    )
    return image


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    PACKAGE_ASSETS.mkdir(parents=True, exist_ok=True)
    image = draw_icon(1024)
    image.save(ASSETS / "icon.png")
    image.resize((512, 512), Image.LANCZOS).save(PACKAGE_ASSETS / "icon.png")
    image.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    png_512 = image.resize((512, 512), Image.LANCZOS)
    try:
        png_512.save(ASSETS / "icon.icns", format="ICNS")
    except Exception as exc:  # pragma: no cover - plugin ICNS tidak selalu ada
        print(f"ICNS dilewati: {exc}")
    print(f"Ikon dibuat di {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
