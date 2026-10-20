"""Galat domain dengan pesan yang bisa ditindaklanjuti pengguna."""

from __future__ import annotations


class DomainError(Exception):
    """Kesalahan yang sudah dipahami aplikasi dan aman ditampilkan ke pengguna."""

    title = "Terjadi kesalahan"

    def __init__(
        self,
        message: str,
        *,
        detail: str = "",
        advice: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.advice = advice

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class InputError(DomainError):
    title = "Masukan tidak valid"


class VideoNotFoundError(InputError):
    title = "Berkas tidak ditemukan"


class UnsupportedVideoError(InputError):
    title = "Berkas bukan video yang didukung"


class MetadataError(InputError):
    title = "Metadata video tidak terbaca"


class InvalidOptionError(InputError):
    title = "Setelan tidak valid"


class OutputNotWritableError(DomainError):
    title = "Folder keluaran tidak dapat ditulis"


class InsufficientDiskSpaceError(DomainError):
    title = "Ruang disk tidak cukup"


class EngineUnavailableError(DomainError):
    title = "Mesin ekstraksi tidak tersedia"


class ExtractionFailedError(DomainError):
    title = "Ekstraksi gagal"

    def __init__(
        self,
        message: str,
        *,
        detail: str = "",
        advice: str = "",
        partial_results: list | None = None,
    ) -> None:
        super().__init__(message, detail=detail, advice=advice)
        self.partial_results = partial_results or []


class PlanError(InputError):
    title = "Tidak ada frame yang bisa diambil"
