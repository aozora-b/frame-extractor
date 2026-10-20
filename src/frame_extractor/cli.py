"""Antarmuka terminal: ``frame-extractor-cli``."""

from __future__ import annotations

import argparse
import contextlib
import signal
import sys
import threading
import time
from pathlib import Path

from . import __version__
from .core.errors import DomainError, InputError
from .core.extract import Engine, extract
from .core.humanize import eta_text, human_bytes, human_duration
from .core.models import ExtractOptions, VideoInfo
from .core.plan import estimate_output_bytes, plan_points
from .core.probe import probe

DEFAULT_TEMPLATE = "{stem}_{index:06d}_{time}.{ext}"

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_PROCESS = 2
EXIT_CANCELLED = 130


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # noqa: D401 - mengikuti kontrak CLI
        self.print_usage(sys.stderr)
        self.exit(EXIT_INPUT, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="frame-extractor-cli",
        description="Ekstrak frame dari satu atau beberapa berkas video tanpa GUI.",
    )
    parser.add_argument("videos", metavar="VIDEO", nargs="+", type=Path)
    parser.add_argument(
        "--mode",
        choices=["interval", "count", "range"],
        default=None,
        help="cara memilih frame (default: interval, atau count bila --count dipakai)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="DETIK",
        help="satu frame tiap N detik (default: 1)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        metavar="N",
        help="jumlah frame tersebar merata; memakai mode count (default: 30)",
    )
    parser.add_argument(
        "--range",
        dest="range_spec",
        metavar="MULAI:AKHIR",
        help="rentang waktu dalam detik, mis. 5:20 atau 5: (sampai akhir)",
    )
    parser.add_argument(
        "--format",
        choices=["png", "jpg"],
        default="png",
        help="format gambar (default: png)",
    )
    parser.add_argument("--quality", type=int, default=95, help="kualitas JPG 1–100")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="FOLDER",
        help="folder keluaran (default: di samping tiap video)",
    )
    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE,
        help=f"pola nama berkas (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "ffmpeg", "opencv"],
        default="auto",
        help="mesin ekstraksi (default: auto)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="tampilkan detail teknis saat terjadi galat",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _parse_range(spec: str | None) -> tuple[float, float | None]:
    if spec is None:
        return 0.0, None
    parts = spec.split(":", 1)
    if len(parts) != 2:
        raise ValueError("Format --range harus MULAI:AKHIR, mis. 5:20.")
    try:
        start = float(parts[0]) if parts[0].strip() else 0.0
        end = float(parts[1]) if parts[1].strip() else None
    except ValueError as exc:
        raise ValueError("Nilai --range harus berupa angka detik.") from exc
    if start < 0 or (end is not None and end <= start):
        raise ValueError("Rentang tidak valid: akhir harus lebih besar dari mulai.")
    return start, end


def _options_for(args: argparse.Namespace) -> ExtractOptions:
    start, end = _parse_range(args.range_spec)
    if args.range_spec:
        mode = "range"
    elif args.mode:
        mode = args.mode
    elif args.count is not None:
        mode = "count"
    else:
        mode = "interval"
    frame_total = args.count if args.count is not None else 30
    return ExtractOptions(
        mode=mode,  # type: ignore[arg-type]
        interval_s=args.interval,
        frame_total=frame_total,
        start_s=start,
        end_s=end,
        fmt=args.format,
        quality=args.quality,
        out_dir=args.out,
        template=args.template,
    )


def _print_info(info: VideoInfo, opt: ExtractOptions, planned: int) -> None:
    size = estimate_output_bytes(info, opt, planned)
    print(f"{info.path.name}")
    print(
        f"  {human_duration(info.duration_s)} · {info.fps:.2f} fps · "
        f"{info.width}×{info.height} · {info.frame_count:,} frame · {info.codec}"
    )
    print(f"  Akan menghasilkan {planned:,} gambar (~{human_bytes(size)})")
    for warning in info.warnings:
        print(f"  Peringatan: {warning}", file=sys.stderr)


class _Progress:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.total = 0
        self.started = time.monotonic()
        self._last_len = 0
        self._ema: float | None = None

    def __call__(self, done: int, total: int, ts: float) -> None:
        if not self.enabled:
            return
        self.total = total
        elapsed = max(1e-6, time.monotonic() - self.started)
        fraction = done / total if total else 0.0
        eta = (elapsed / done) * (total - done) if done > 0 else None
        if eta is not None:
            self._ema = eta if self._ema is None else 0.7 * self._ema + 0.3 * eta
        line = f"  {fraction * 100:3.0f}%  {done}/{total}  {eta_text(self._ema)}"
        padding = " " * max(0, self._last_len - len(line))
        print(f"\r{line}{padding}", end="", file=sys.stderr, flush=True)
        self._last_len = len(line)

    def finish(self) -> None:
        if self.enabled and self._last_len:
            print(file=sys.stderr)


def _run_one(
    path: Path,
    opt: ExtractOptions,
    engine: Engine,
    cancel: threading.Event,
    verbose: bool,
) -> tuple[int, int, int]:
    """Kembalikan (jumlah hasil, ukuran total, kode keluar)."""

    info = probe(path)
    planned_points = plan_points(info, opt)
    _print_info(info, opt, len(planned_points))

    progress = _Progress()
    started = time.monotonic()
    try:
        results = extract(
            info,
            opt,
            on_progress=progress,
            should_cancel=cancel.is_set,
            engine=engine,
        )
    finally:
        progress.finish()

    total_size = sum(result.size_bytes for result in results)
    elapsed = time.monotonic() - started

    if cancel.is_set():
        print(
            f"Dibatalkan: {len(results)} dari {len(planned_points)} gambar tersimpan "
            f"({human_bytes(total_size)}, {human_duration(elapsed)}).",
            file=sys.stderr,
        )
        return len(results), total_size, EXIT_CANCELLED

    if not results:
        print("Tidak ada gambar yang dihasilkan.", file=sys.stderr)
        return 0, 0, EXIT_PROCESS

    folders = sorted({str(result.path.parent) for result in results})
    print(
        f"Selesai: {len(results)} gambar · {human_bytes(total_size)} · "
        f"{human_duration(elapsed)}"
    )
    for folder in folders:
        print(f"  Disimpan di: {folder}")
    print("  " + "\n  ".join(str(result.path.name) for result in results[:3]))
    if len(results) > 3:
        print(f"  … dan {len(results) - 3} berkas lainnya")
    return len(results), total_size, EXIT_OK


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        opt = _options_for(args)
    except (ValueError, DomainError) as exc:
        print(f"Masukan tidak valid: {exc}", file=sys.stderr)
        return EXIT_INPUT

    cancel = threading.Event()
    previous_handler = signal.getsignal(signal.SIGINT)

    def handle_interrupt(signum, frame) -> None:  # noqa: ANN001, ARG001
        if cancel.is_set():
            raise KeyboardInterrupt
        cancel.set()
        print("\nMembatalkan… (Ctrl+C lagi untuk keluar paksa)", file=sys.stderr)

    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGINT, handle_interrupt)

    total_files = 0
    total_size = 0
    exit_code = EXIT_OK
    started = time.monotonic()

    try:
        for path in args.videos:
            if cancel.is_set():
                exit_code = EXIT_CANCELLED
                break
            try:
                count, size, code = _run_one(
                    path, opt, args.engine, cancel, args.verbose  # type: ignore[arg-type]
                )
            except DomainError as exc:
                exit_code = max(exit_code, EXIT_INPUT if isinstance(exc, InputError) else EXIT_PROCESS)
                print(f"{exc.title}: {exc.message}", file=sys.stderr)
                if exc.advice:
                    print(f"  Saran: {exc.advice}", file=sys.stderr)
                if args.verbose and exc.detail:
                    print(f"  Detail: {exc.detail}", file=sys.stderr)
                if cancel.is_set():
                    exit_code = EXIT_CANCELLED
                    break
                continue
            except KeyboardInterrupt:  # pragma: no cover - interaksi pengguna
                print("\nKeluar paksa.", file=sys.stderr)
                exit_code = EXIT_CANCELLED
                break

            total_files += count
            total_size += size
            exit_code = max(exit_code, code)
            if code == EXIT_CANCELLED:
                break

        if args.videos and len(args.videos) > 1:
            print(
                f"Total: {total_files} gambar · {human_bytes(total_size)} · "
                f"{human_duration(time.monotonic() - started)}"
            )
    finally:
        with contextlib.suppress(ValueError):
            signal.signal(signal.SIGINT, previous_handler)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
