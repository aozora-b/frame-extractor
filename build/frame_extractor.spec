# -*- mode: python ; coding: utf-8 -*-
"""Build PyInstaller mode --onedir (utama)."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
ASSETS = ROOT / "assets"
SRC = ROOT / "src"
FFMPEG = ROOT / "third_party" / "ffmpeg" / "bin"

cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all("cv2")

datas = [
    (str(SRC / "frame_extractor" / "ui" / "theme.qss"), "frame_extractor/ui"),
    (str(SRC / "frame_extractor" / "assets"), "frame_extractor/assets"),
    (str(FFMPEG), "ffmpeg/bin"),
    *cv2_datas,
]
binaries = [*cv2_binaries]
hiddenimports = [*cv2_hiddenimports]

if sys.platform == "win32":
    icon = str(ASSETS / "icon.ico")
    version_file = str(ROOT / "build" / "version_info.txt")
elif sys.platform == "darwin":
    icon = str(ASSETS / "icon.icns")
    version_file = None
else:
    icon = str(ASSETS / "icon.png")
    version_file = None

a = Analysis(
    [str(ROOT / "build" / "entry.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Frame Extractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=version_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Frame Extractor",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Frame Extractor.app",
        icon=str(ASSETS / "icon.icns"),
        bundle_identifier="com.frameextractor.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
