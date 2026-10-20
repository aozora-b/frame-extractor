"""Paketkan hasil build PyInstaller menjadi aset rilis + checksum."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_FILES = ("LICENSE", "THIRD-PARTY-NOTICES.md", "README.md")


def _arch() -> str:
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64", "x64"):
        return "x64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return machine or "unknown"


def _copy_docs(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in DOC_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    licenses = ROOT / "licenses"
    if licenses.is_dir():
        shutil.copytree(licenses, destination / "licenses", dirs_exist_ok=True)


def _zip_folder(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(Path(source.name) / path.relative_to(source)))


def _tar_folder(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        archive.add(source, arcname=source.name)


def _zip_onefile(exe: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frame-extractor-onefile-") as temp:
        staging = Path(temp) / "Frame Extractor"
        staging.mkdir()
        shutil.copy2(exe, staging / exe.name)
        _copy_docs(staging)
        _zip_folder(staging, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package(onedir: Path | None, onefile: Path | None, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    system = sys.platform
    arch = _arch()
    produced: list[Path] = []

    if onedir is not None and onedir.is_dir():
        if system == "darwin" and onedir.suffix == ".app":
            _copy_docs(onedir / "Contents" / "Resources")
            asset = output / f"frame-extractor-macos-{arch}.zip"
            _zip_folder(onedir, asset)
        else:
            _copy_docs(onedir)
            if system == "win32":
                asset = output / f"frame-extractor-windows-{arch}.zip"
                _zip_folder(onedir, asset)
            elif system == "darwin":
                asset = output / f"frame-extractor-macos-{arch}.zip"
                _zip_folder(onedir, asset)
            else:
                asset = output / f"frame-extractor-linux-{arch}.tar.gz"
                _tar_folder(onedir, asset)
        produced.append(asset)

    if onefile is not None and onefile.is_file() and system == "win32":
        asset = output / f"frame-extractor-windows-{arch}-onefile.zip"
        _zip_onefile(onefile, asset)
        produced.append(asset)

    checksums = output / "SHA256SUMS.txt"
    lines = [f"{_sha256(path)}  {path.name}" for path in produced]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    produced.append(checksums)
    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buat ZIP/TAR.GZ rilis dan checksum.")
    parser.add_argument("--onedir", type=Path, default=ROOT / "dist" / "Frame Extractor")
    parser.add_argument(
        "--onefile", type=Path, default=ROOT / "dist-onefile" / "Frame Extractor.exe"
    )
    parser.add_argument("--out", type=Path, default=ROOT / "dist-release")
    args = parser.parse_args(argv)

    onedir = args.onedir
    if sys.platform == "darwin" and (ROOT / "dist" / "Frame Extractor.app").is_dir():
        onedir = ROOT / "dist" / "Frame Extractor.app"

    produced = package(
        onedir if onedir.exists() else None,
        args.onefile if args.onefile.exists() else None,
        args.out,
    )
    for path in produced:
        print(f"{path.name}\t{path.stat().st_size:,} byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
