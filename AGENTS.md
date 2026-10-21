# Frame Extractor — Agent Guidelines & Architecture

## Context & Architecture
- **Purpose**: Fast desktop GUI application for extracting frames from videos into PNG/JPG formats.
- **Tech Stack**: Python 3.12, PySide6 (Qt 6.12), OpenCV 5, FFmpeg n8.1 (LGPL shared), PyInstaller 6.
- **Repo & Releases**: [github.com/aozora-b/frame-extractor](https://github.com/aozora-b/frame-extractor) (Release v1.0.0).

## Release & Build Notes
- Release binaries are built using PyInstaller with `build/frame_extractor.spec` and `build/frame_extractor_onefile.spec`.
- Artifacts are packaged into `dist-release/`:
  - `frame-extractor-v1.0.0-windows-x64.zip` (Onedir)
  - `frame-extractor-v1.0.0-windows-x64-onefile.zip` (Onefile)
  - `SHA256SUMS.txt`
- Uploading releases is handled by `python tools/upload_release.py`.
- Platform support: Windows x64 tested & released; Linux/macOS planned.
