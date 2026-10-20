from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "frame_extractor.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        timeout=120,
    )


def test_help_is_readable() -> None:
    completed = run_cli("--help")
    assert completed.returncode == 0
    text = completed.stdout
    for expected in ("--mode", "--interval", "--count", "--range", "--format", "--out"):
        assert expected in text


def test_version() -> None:
    completed = run_cli("--version")
    assert completed.returncode == 0
    assert "1.0.0" in completed.stdout


@pytest.mark.integration
def test_extract_interval(test_video: Path, tmp_path: Path) -> None:
    out = tmp_path / "keluaran"
    completed = run_cli(
        str(test_video),
        "--mode",
        "interval",
        "--interval",
        "2",
        "--out",
        str(out),
    )
    assert completed.returncode == 0, completed.stderr
    files = sorted(out.glob("*.png"))
    assert len(files) == 5
    assert files[0].name == "sample_000001_00-00-00.png"
    assert files[-1].name == "sample_000005_00-00-08.png"
    assert "Selesai: 5 gambar" in completed.stdout


@pytest.mark.integration
def test_extract_range(test_video: Path, tmp_path: Path) -> None:
    out = tmp_path / "range"
    completed = run_cli(
        str(test_video),
        "--range",
        "2:6",
        "--interval",
        "2",
        "--out",
        str(out),
    )
    assert completed.returncode == 0, completed.stderr
    assert len(list(out.glob("*.jpg"))) == 0
    files = sorted(out.glob("*.png"))
    assert len(files) == 2
    assert files[0].name == "sample_000001_00-00-02.png"


@pytest.mark.integration
def test_extract_jpg(test_video: Path, tmp_path: Path) -> None:
    out = tmp_path / "jpg"
    completed = run_cli(
        str(test_video),
        "--count",
        "3",
        "--format",
        "jpg",
        "--quality",
        "60",
        "--out",
        str(out),
    )
    assert completed.returncode == 0, completed.stderr
    assert len(list(out.glob("*.jpg"))) == 3


def test_missing_file_exit_one(tmp_path: Path) -> None:
    completed = run_cli(str(tmp_path / "tidak-ada.mp4"))
    assert completed.returncode == 1
    assert "tidak ditemukan" in completed.stderr.lower()


def test_invalid_option_exit_one(test_video: Path) -> None:
    completed = run_cli(str(test_video), "--count", "0")
    assert completed.returncode == 1
    assert "tidak valid" in completed.stderr.lower() or "minimal" in completed.stderr.lower()


def test_bad_range_syntax_exit_one(test_video: Path) -> None:
    completed = run_cli(str(test_video), "--range", "5-10")
    assert completed.returncode == 1
    assert "range" in completed.stderr.lower()


def test_corrupt_file_exit_one(tmp_path: Path) -> None:
    bad = tmp_path / "rusak.mp4"
    bad.write_bytes(b"bukan video" * 100)
    completed = run_cli(str(bad))
    assert completed.returncode == 1
    assert "metadata" in completed.stderr.lower() or "terbaca" in completed.stderr.lower()
