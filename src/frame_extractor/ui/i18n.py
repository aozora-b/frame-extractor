"""Katalog terjemahan ringan untuk antarmuka Frame Extractor.

Bahasa sumber adalah Bahasa Indonesia. Setiap teks UI yang ingin didukung
dalam bahasa Inggris didaftarkan di ``_ENGLISH`` dengan teks Indonesia sebagai
kunci. Nilai dapat berupa string biasa atau pasangan ``(tunggal, jamak)`` yang
dipilih berdasarkan argumen ``n`` pada :func:`tr`.

Pendekatan ini sengaja tidak memakai berkas ``.qm`` agar build PyInstaller
tetap sederhana dan perubahan bahasa bisa diterapkan langsung tanpa restart.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import suppress
from typing import TypeAlias

from PySide6.QtCore import QObject, Signal

DEFAULT_LANGUAGE = "id"
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("id", "Bahasa Indonesia"),
    ("en", "English"),
)

Translation: TypeAlias = str | tuple[str, str]

# ---------------------------------------------------------------------------
# Teks antarmuka
# ---------------------------------------------------------------------------
_ENGLISH: dict[str, Translation] = {
    # Header dan jendela utama
    "Ambil gambar diam dari video": "Extract still frames from video",
    "Tema": "Theme",
    "Ganti tema terang/gelap": "Switch light/dark theme",
    "Ganti tema": "Change theme",
    "terang": "light",
    "gelap": "dark",
    "Tema saat ini: {theme}. Klik untuk beralih ke {target}.": (
        "Current theme: {theme}. Click to switch to {target}."
    ),
    "Info": "Info",
    "Tentang aplikasi dan pintasan keyboard": "About the app and keyboard shortcuts",
    "Tentang aplikasi": "About the app",
    "Progres ekstraksi": "Extraction progress",
    "Hentikan proses (Esc); hasil yang sudah tersimpan tetap ada": (
        "Stop the process (Esc); frames that are already saved stay available"
    ),
    "Batal": "Cancel",
    "Batalkan ekstraksi": "Cancel extraction",
    # Menu
    "Berkas": "File",
    "Buka video…": "Open video…",
    "Tambah ke antrean…": "Add to queue…",
    "Keluar": "Quit",
    "Ekstraksi": "Extraction",
    "Mulai ekstraksi": "Start extraction",
    "Batalkan": "Cancel",
    "Buka folder hasil": "Open results folder",
    "Tampilan": "View",
    "Tema gelap": "Dark theme",
    "Panel log": "Log panel",
    "Bantuan": "Help",
    "Pintasan keyboard": "Keyboard shortcuts",
    "Tentang Frame Extractor": "About Frame Extractor",
    "Bahasa": "Language",
    "Bahasa Indonesia": "Indonesian",
    "English": "English",
    "Log": "Log",
    "Log aplikasi": "Application log",
    # Zona jatuh
    "Zona jatuh berkas video": "Video drop zone",
    "Jatuhkan berkas video atau folder ke sini, atau tekan Enter untuk memilih berkas.": (
        "Drop video files or folders here, or press Enter to choose files."
    ),
    "Jatuhkan video atau folder di sini": "Drop a video or folder here",
    "atau klik area ini untuk memilih berkas dari komputer": (
        "or click this area to choose a file from your computer"
    ),
    "MP4 · MKV · MOV · WebM · AVI · MPEG · MTS · dan lainnya": (
        "MP4 · MKV · MOV · WebM · AVI · MPEG · MTS · and more"
    ),
    "Pilih video": "Choose video",
    "Buka dialog pemilih berkas (Ctrl+O)": "Open the file picker (Ctrl+O)",
    "Pilih folder": "Choose folder",
    "Tambahkan semua video di dalam sebuah folder": "Add every video in a folder",
    # Kartu video
    "VIDEO": "VIDEO",
    "Belum ada video": "No video selected",
    "durasi": "duration",
    "frame/detik": "frames/second",
    "resolusi": "resolution",
    "total frame": "total frames",
    "codec": "codec",
    # Antrean
    "Antrean": "Queue",
    "Tambah video": "Add video",
    "Tambahkan video lain ke antrean (Ctrl+Shift+O)": (
        "Add another video to the queue (Ctrl+Shift+O)"
    ),
    "Hapus": "Remove",
    "Hapus video terpilih dari antrean (Delete)": (
        "Remove the selected video from the queue (Delete)"
    ),
    "Hapus video dari antrean": "Remove video from queue",
    "Antrean video": "Video queue",
    "Hapus dari antrean": "Remove from queue",
    "{n} video": ("{n} video", "{n} videos"),
    "Menunggu": "Waiting",
    "Membaca metadata…": "Reading metadata…",
    "Siap": "Ready",
    "Memproses…": "Processing…",
    "Selesai": "Done",
    "Gagal": "Failed",
    "Dibatalkan": "Cancelled",
    "Tidak dijalankan": "Not run",
    "{duration} · {width}×{height}": "{duration} · {width}×{height}",
    "{n} gambar · {size}": ("{n} frame · {size}", "{n} frames · {size}"),
    "{saved} dari {n} gambar tersimpan": (
        "{saved} of {n} frame saved",
        "{saved} of {n} frames saved",
    ),
    "{n} gambar tersimpan": ("{n} frame saved", "{n} frames saved"),
    "{n} gambar": ("{n} frame", "{n} frames"),
    "{n} gambar yang sudah selesai tetap tersimpan.": (
        "{n} frame that was already finished is still saved.",
        "{n} frames that were already finished are still saved.",
    ),
    # Panel setelan
    "Setelan": "Settings",
    "Satu frame tiap N detik": "One frame every N seconds",
    "N frame tersebar merata": "N frames evenly spaced",
    "Rentang waktu tertentu": "Specific time range",
    "Mode pengambilan frame": "Frame capture mode",
    "Mode": "Mode",
    "Ambil satu frame setiap N detik": "Capture one frame every N seconds",
    "Jumlah frame yang disebar merata sepanjang video": (
        "Number of frames distributed evenly across the video"
    ),
    "Awal rentang yang diambil": "Start of the captured range",
    "Akhir rentang (tidak termasuk)": "End of the range (exclusive)",
    "Tiap": "Every",
    "Jumlah": "Count",
    "Mulai": "Start",
    "Akhir": "End",
    "PNG — lossless": "PNG — lossless",
    "JPG — lebih kecil": "JPG — smaller",
    "Format gambar": "Image format",
    "Format": "Format",
    "Kualitas JPG": "JPG quality",
    "Kualitas JPEG": "JPEG quality",
    "Slider kualitas JPEG": "JPEG quality slider",
    "Di samping berkas video": "Next to the video file",
    "Folder keluaran": "Output folder",
    "Kosongkan untuk menyimpan di folder yang sama dengan video": (
        "Leave empty to save in the same folder as the video"
    ),
    "Pilih folder keluaran": "Choose output folder",
    "PERKIRAAN": "ESTIMATE",
    "Pilih video untuk melihat perkiraan.": "Choose a video to see an estimate.",
    "Ctrl+Enter untuk mulai · Esc untuk membatalkan": (
        "Ctrl+Enter to start · Esc to cancel"
    ),
    "Mulai mengekstrak semua video di antrean (Ctrl+Enter)": (
        "Start extracting every video in the queue (Ctrl+Enter)"
    ),
    "Siap diekstrak.": "Ready to extract.",
    " dtk": " s",
    # Galeri
    "Hasil": "Results",
    "Belum ada hasil": "No results yet",
    "Buka folder": "Open folder",
    "Buka folder hasil di pengelola berkas": (
        "Open the results folder in the file manager"
    ),
    "Galeri hasil ekstraksi": "Extraction results gallery",
    "Belum ada gambar. Jalankan ekstraksi untuk melihat hasil.": (
        "No frames yet. Run an extraction to see results."
    ),
    "memuat…": "loading…",
    "Tidak ada gambar yang dihasilkan": "No frames were produced",
    "Waktu {time} · {size}": "Time {time} · {size}",
    "Dibatalkan · {n} dari {total} gambar tersimpan · {size}": (
        "Cancelled · {n} of {total} frame saved · {size}",
        "Cancelled · {n} of {total} frames saved · {size}",
    ),
    "Dibatalkan · {n} gambar tersimpan · {size}": (
        "Cancelled · {n} frame saved · {size}",
        "Cancelled · {n} frames saved · {size}",
    ),
    "{n} gambar · {size} · {duration}": (
        "{n} frame · {size} · {duration}",
        "{n} frames · {size} · {duration}",
    ),
    # Status dan footer
    "Siap — pilih video untuk memulai": "Ready — choose a video to start",
    "Antrean kosong — pilih video untuk memulai": (
        "Queue is empty — choose a video to start"
    ),
    "{name} · siap diekstrak": "{name} · ready to extract",
    "Membaca metadata {name}…": "Reading metadata for {name}…",
    "{n} video di antrean": ("{n} video in the queue", "{n} videos in the queue"),
    "Semua video tersebut sudah ada di antrean": "All of those videos are already in the queue",
    "Video dihapus · tersisa {n} video": (
        "Video removed · {n} video remaining",
        "Video removed · {n} videos remaining",
    ),
    "Menyiapkan ekstraksi…": "Preparing extraction…",
    "Mengekstrak {name}…": "Extracting {name}…",
    "Memeriksa {name}…": "Checking {name}…",
    "Menyimpan hasil…": "Saving results…",
    "Membatalkan ekstraksi…": "Cancelling extraction…",
    "Membatalkan…": "Cancelling…",
    "Dibatalkan · {n} gambar tersimpan": (
        "Cancelled · {n} frame saved",
        "Cancelled · {n} frames saved",
    ),
    "Dibatalkan · tidak ada gambar tersimpan": "Cancelled · no frames saved",
    "Selesai dengan galat: {errors} · {n} gambar": (
        "Completed with errors: {errors} · {n} frame",
        "Completed with errors: {errors} · {n} frames",
    ),
    "Ekstraksi gagal · lihat pesan galat": "Extraction failed · see the error message",
    "Selesai · {n} gambar · {size}": (
        "Done · {n} frame · {size}",
        "Done · {n} frames · {size}",
    ),
    "Tambahkan video terlebih dahulu": "Add a video first",
    "Setelan belum valid": "Settings are not valid",
    "Semua video di antrean sudah selesai — hapus lalu tambahkan lagi untuk mengulang": (
        "Every video in the queue is finished — remove them and add them again to repeat"
    ),
    "menghitung sisa waktu…": "calculating remaining time…",
    "menghentikan…": "stopping…",
    "dibatalkan": "cancelled",
    "selesai dengan galat": "finished with errors",
    "selesai": "done",
    # Dialog
    "Pilih folder video": "Choose video folder",
    "Berkas video (*.mp4 *.m4v *.mkv *.mov *.webm *.avi *.wmv *.flv *.mpg *.mpeg *.mts *.m2ts *.ts *.3gp *.3g2 *.ogv *.ogg *.asf *.vob *.f4v *.mxf);;Semua berkas (*)": (
        "Video files (*.mp4 *.m4v *.mkv *.mov *.webm *.avi *.wmv *.flv *.mpg "
        "*.mpeg *.mts *.m2ts *.ts *.3gp *.3g2 *.ogv *.ogg *.asf *.vob *.f4v "
        "*.mxf);;All files (*)"
    ),
    "Sedang memproses": "Currently processing",
    "Tunggu hingga proses selesai atau batalkan sebelum menambah video.": (
        "Wait until processing finishes or cancel it before adding more videos."
    ),
    "Folder kosong": "Empty folder",
    "Tidak ada berkas video yang didukung di folder tersebut.": (
        "There are no supported video files in that folder."
    ),
    "Bukan video": "Not a video",
    "Pilih berkas video seperti MP4, MKV, MOV, WebM, atau AVI.": (
        "Choose a video file such as MP4, MKV, MOV, WebM, or AVI."
    ),
    "Sebagian berkas dilewati": "Some files were skipped",
    "{n} berkas dilewati karena bukan video yang didukung.": (
        "{n} file was skipped because it is not a supported video.",
        "{n} files were skipped because they are not supported videos.",
    ),
    "{n} folder tidak berisi video.": (
        "{n} folder contains no videos.",
        "{n} folders contain no videos.",
    ),
    "Folder tidak ditemukan": "Folder not found",
    "Folder hasil tidak lagi tersedia:\n{folder}": (
        "The results folder is no longer available:\n{folder}"
    ),
    "Buka video": "Open video",
    "Tambah video ke antrean": "Add a video to the queue",
    "Hapus video terpilih dari antrean": "Remove the selected video from the queue",
    "Buka/tutup panel log": "Open/close the log panel",
    "Tentang {name}": "About {name}",
    "Ekstrak frame dari video menjadi PNG atau JPG.": (
        "Extract frames from videos as PNG or JPG."
    ),
    "Lisensi aplikasi: MIT. Antarmuka memakai Qt for Python (PySide6, LGPLv3). Mesin ekstraksi memakai ffmpeg (LGPL) dan OpenCV (Apache 2.0).": (
        "Application license: MIT. The interface uses Qt for Python "
        "(PySide6, LGPLv3). The extraction engine uses ffmpeg (LGPL) and "
        "OpenCV (Apache 2.0)."
    ),
    "Log: {path}": "Log: {path}",
    "Ekstraksi sedang berjalan": "Extraction is running",
    "Kesalahan tak terduga": "Unexpected error",
    "Aplikasi mengalami kesalahan yang tidak terduga.\n\nDetail lengkap tercatat di log:\n{path}\n\nAnda dapat melanjutkan, tetapi sebaiknya simpan pekerjaan dan jalankan ulang aplikasi.": (
        "The application encountered an unexpected error.\n\nThe full "
        "details are in the log:\n{path}\n\nYou can continue, but it is "
        "best to save your work and restart the application."
    ),
    "Aplikasi gagal dimulai": "The application failed to start",
    "Jendela utama tidak dapat dibuka.\n\nDetail lengkap tercatat di log:\n{path}": (
        "The main window could not be opened.\n\nThe full details are in "
        "the log:\n{path}"
    ),
    "Hentikan ekstraksi dan keluar?\n\nGambar yang sudah tersimpan tidak akan dihapus.": (
        "Stop the extraction and quit?\n\nFrames that are already saved will not be deleted."
    ),
    # Dialog galat
    "Saran: {advice}": "Advice: {advice}",
    "Tampilkan detail teknis": "Show technical details",
    "Sembunyikan detail teknis": "Hide technical details",
    "Salin detail": "Copy details",
    "Tutup": "Close",
    # Judul galat domain
    "Terjadi kesalahan": "Something went wrong",
    "Masukan tidak valid": "Invalid input",
    "Berkas tidak ditemukan": "File not found",
    "Berkas bukan video yang didukung": "Unsupported video file",
    "Metadata video tidak terbaca": "Could not read video metadata",
    "Setelan tidak valid": "Invalid settings",
    "Folder keluaran tidak dapat ditulis": "Output folder is not writable",
    "Ruang disk tidak cukup": "Not enough disk space",
    "Mesin ekstraksi tidak tersedia": "Extraction engine unavailable",
    "Ekstraksi gagal": "Extraction failed",
    "Tidak ada frame yang bisa diambil": "No frames can be captured",
    # Pesan dan saran galat yang umum
    "Periksa apakah berkas dipindahkan atau namanya berubah.": (
        "Check whether the file was moved or renamed."
    ),
    "Pilih berkas video, bukan folder.": "Choose a video file, not a folder.",
    "Pilih berkas video seperti MP4, MKV, MOV, atau WebM.": (
        "Choose a video file such as MP4, MKV, MOV, or WebM."
    ),
    "Pastikan berkas tidak rusak dan codec-nya didukung. Coba buka video di pemutar lain, atau pasang ffmpeg.": (
        "Make sure the file is not damaged and its codec is supported. Try "
        "opening the video in another player, or install ffmpeg."
    ),
    "Berkas ini mungkin hanya berisi audio atau gambar sampul.": (
        "This file may contain only audio or a cover image."
    ),
    "ffprobe tidak dapat membaca berkas.": "ffprobe could not read the file.",
    "Keluaran ffprobe bukan JSON yang valid.": "ffprobe returned invalid JSON.",
    "OpenCV tidak terpasang, sehingga cadangan pembacaan metadata tidak tersedia.": (
        "OpenCV is not installed, so the metadata reader fallback is unavailable."
    ),
    "OpenCV tidak dapat membuka berkas video ini.": "OpenCV could not open this video file.",
    "OpenCV tidak dapat membaca frame pertama video ini.": (
        "OpenCV could not read the first frame of this video."
    ),
    "Frame rate video tidak terbaca oleh OpenCV.": (
        "OpenCV could not read the video frame rate."
    ),
    "Jumlah frame video tidak terbaca oleh OpenCV.": (
        "OpenCV could not read the video frame count."
    ),
    "Durasi video tidak terbaca oleh OpenCV.": "OpenCV could not read the video duration.",
    "Resolusi video tidak terbaca.": "Could not read the video resolution.",
    "Video ini tampaknya memiliki frame rate variabel (VFR); timestamp hasil ekstraksi bersifat perkiraan.": (
        "This video appears to use a variable frame rate (VFR); extracted "
        "frame timestamps are approximate."
    ),
    "Video ini lebih dari 2 jam; ekstraksi bisa memakan waktu lama.": (
        "This video is longer than 2 hours; extraction may take a long time."
    ),
    "Video ini lebih dari 2 jam. Perkiraan waktu ekstraksi ± {duration}; proses berjalan di latar belakang.": (
        "This video is longer than 2 hours. Estimated extraction time ± "
        "{duration}; the process runs in the background."
    ),
    "Durasi video tidak terbaca, sehingga titik sampel tidak dapat dihitung.": (
        "The video duration could not be read, so sample points cannot be calculated."
    ),
    "Coba berkas video lain atau periksa apakah berkas rusak.": (
        "Try another video file or check whether the file is damaged."
    ),
    "Waktu mulai berada di luar durasi video.": "The start time is outside the video duration.",
    "Durasi video ini {duration:.1f} detik; turunkan waktu mulai.": (
        "This video is {duration:.1f} seconds long; lower the start time."
    ),
    "Rentang waktu tidak menyisakan satu frame pun.": (
        "The time range does not leave room for a single frame."
    ),
    "Perlebar rentang waktu atau turunkan waktu mulai.": (
        "Widen the time range or lower the start time."
    ),
    "Jumlah frame harus minimal 1.": "The frame count must be at least 1.",
    "Jumlah frame terlalu banyak ({count:,}). Batas aman {limit:,}.": (
        "Too many frames requested ({count:,}). The safe limit is {limit:,}."
    ),
    "Kurangi jumlah frame yang diminta.": "Reduce the requested frame count.",
    "Interval harus lebih besar dari 0 detik.": "The interval must be greater than 0 seconds.",
    "Interval terlalu rapat: akan menghasilkan {count:,} frame (batas {limit:,}).": (
        "The interval is too small: it would produce {count:,} frames (limit {limit:,})."
    ),
    "Perbesar interval atau perkecil rentang waktu.": (
        "Increase the interval or reduce the time range."
    ),
    "Tidak ada frame yang bisa diambil dengan setelan ini.": (
        "No frames can be captured with these settings."
    ),
    "Perlebar rentang waktu atau perkecil interval.": (
        "Widen the time range or reduce the interval."
    ),
    "Pola nama berkas tidak boleh kosong.": "The filename pattern cannot be empty.",
    "Pola nama berkas harus memuat {index} dan {ext}.": (
        "The filename pattern must contain {index} and {ext}."
    ),
    "Pola nama berkas harus memuat {index} agar urutan konsisten.": (
        "The filename pattern must contain {index} to keep the order consistent."
    ),
    "Pola nama berkas harus memuat {ext}.": "The filename pattern must contain {ext}.",
    "Folder keluaran tidak valid.": "The output folder is invalid.",
    "Folder keluaran tidak dapat dibuat: {path}": "Could not create the output folder: {path}",
    "Folder keluaran bukan folder: {path}": "The output path is not a folder: {path}",
    "Folder keluaran tidak dapat ditulis: {path}": "The output folder is not writable: {path}",
    "Pilih folder lain yang Anda punya izin menulisnya.": (
        "Choose another folder that you have permission to write to."
    ),
    "Pilih folder, bukan berkas.": "Choose a folder, not a file.",
    "Pilih folder lain, atau ubah izin folder tersebut.": (
        "Choose another folder, or change that folder's permissions."
    ),
    "Ruang disk tidak cukup untuk hasil ekstraksi.": (
        "There is not enough disk space for the extraction results."
    ),
    "Kosongkan disk, pilih folder lain, atau kurangi jumlah frame.": (
        "Free up disk space, choose another folder, or reduce the frame count."
    ),
    "Pilih folder keluaran lain atau hapus hasil lama.": (
        "Choose another output folder or delete old results."
    ),
    "Folder sementara untuk ekstraksi tidak dapat dibuat.": (
        "Could not create the temporary extraction folder."
    ),
    "Periksa izin folder keluaran dan ruang disk, lalu coba lagi.": (
        "Check the output folder permissions and disk space, then try again."
    ),
    "Nama folder sementara tidak dapat dibuat.": (
        "Could not create the temporary folder name."
    ),
    "Coba lagi; jika tetap gagal, pilih folder keluaran lain.": (
        "Try again; if it still fails, choose another output folder."
    ),
    "ffmpeg tidak dapat dijalankan.": "ffmpeg could not be started.",
    "Pastikan ffmpeg tidak diblokir antivirus dan berkasnya lengkap.": (
        "Make sure ffmpeg is not blocked by antivirus and that the file is complete."
    ),
    "Waktu mulai tidak boleh negatif.": "Start time cannot be negative.",
    "Waktu selesai harus lebih besar dari waktu mulai.": (
        "End time must be greater than the start time."
    ),
    "Kualitas JPG harus di antara 1 dan 100.": (
        "JPG quality must be between 1 and 100."
    ),
    "Terlalu banyak nama berkas yang bentrok.": (
        "Too many conflicting filenames."
    ),
    "index harus dimulai dari 1": "index must start at 1",
    "Durasi atau frame rate video tidak terbaca.": (
        "The video duration or frame rate could not be read."
    ),
    "Pasang ffmpeg, atau gunakan mesin OpenCV yang ikut terpasang.": (
        "Install ffmpeg, or use the bundled OpenCV engine."
    ),
    "Pasang ffmpeg atau OpenCV, lalu jalankan ulang aplikasi.": (
        "Install ffmpeg or OpenCV, then restart the application."
    ),
    "Pasang ulang aplikasi, atau pasang ffmpeg dan gunakan mesin utama.": (
        "Reinstall the application, or install ffmpeg and use the main engine."
    ),
    "Coba format PNG, atau periksa ruang disk.": (
        "Try the PNG format, or check the disk space."
    ),
    "Periksa izin folder dan ruang disk.": "Check the folder permissions and disk space.",
    "Gunakan ffmpeg atau konversi video terlebih dahulu.": (
        "Use ffmpeg or convert the video first."
    ),
    "Codec ini mungkin tidak didukung OpenCV. Pasang ffmpeg atau konversi video ke MP4/H.264.": (
        "OpenCV may not support this codec. Install ffmpeg or convert the "
        "video to MP4/H.264."
    ),
    "ffmpeg tidak ditemukan.": "ffmpeg was not found.",
    "Pasang ffmpeg dan pastikan ada di PATH, atau gunakan mesin OpenCV. Versi rilis aplikasi sudah menyertakan ffmpeg.": (
        "Install ffmpeg and make sure it is on PATH, or use the OpenCV engine. "
        "Release builds already include ffmpeg."
    ),
    "ffmpeg berhenti dengan kode {code}.": "ffmpeg exited with code {code}.",
    "Codec mungkin tidak didukung. Aplikasi akan mencoba mesin OpenCV; bila tetap gagal, coba konversi video ke MP4/H.264.": (
        "The codec may not be supported. The app will try the OpenCV engine; "
        "if it still fails, convert the video to MP4/H.264."
    ),
    "Hanya {done} dari {total} frame yang berhasil dibuat.": (
        "Only {done} of {total} frames were created successfully."
    ),
    "Video mungkin lebih pendek dari metadata, atau codec-nya bermasalah. Coba kurangi jumlah frame atau gunakan mesin OpenCV.": (
        "The video may be shorter than its metadata, or the codec may have "
        "problems. Reduce the frame count or use the OpenCV engine."
    ),
    "OpenCV tidak terpasang, sehingga mesin cadangan tidak tersedia.": (
        "OpenCV is not installed, so the fallback engine is unavailable."
    ),
    "Gambar tidak dapat dikodekan sebagai {format}.": (
        "The image could not be encoded as {format}."
    ),
    "Hasil tidak dapat disimpan: {name}": "Could not save the result: {name}",
    "OpenCV tidak dapat membuka {name}.": "OpenCV could not open {name}.",
    "OpenCV tidak dapat membaca frame rate video.": (
        "OpenCV could not read the video frame rate."
    ),
    "Hanya {done} dari {total} frame yang berhasil dibaca.": (
        "Only {done} of {total} frames were read successfully."
    ),
    "Video mungkin lebih pendek dari metadata atau memakai codec yang tidak didukung. Coba ffmpeg atau konversi video ke MP4/H.264.": (
        "The video may be shorter than its metadata or use an unsupported "
        "codec. Try ffmpeg or convert the video to MP4/H.264."
    ),
    "Tidak ada mesin ekstraksi yang tersedia.": "No extraction engine is available.",
    "Tidak ada mesin yang berhasil mengekstrak video ini.": (
        "No engine could extract this video."
    ),
    "Codec mungkin tidak didukung. Coba konversi video ke MP4/H.264, atau periksa apakah berkas benar-benar utuh.": (
        "The codec may not be supported. Try converting the video to "
        "MP4/H.264, or check whether the file is intact."
    ),
}

# Pola pesan yang memuat nama berkas, angka, atau detail lain.
_PATTERNS_EN: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^Berkas tidak ditemukan: (.+)$"), r"File not found: \1"),
    (re.compile(r"^Bukan berkas: (.+)$"), r"Not a file: \1"),
    (re.compile(r"^Format berkas tidak didukung: (.+)$"), r"Unsupported file format: \1"),
    (re.compile(r"^Metadata video tidak terbaca: (.+)$"), r"Could not read video metadata: \1"),
    (re.compile(r"^Tidak ada aliran video di dalam (.+)\.$"), r"No video stream found in \1."),
    (re.compile(r"^Folder keluaran tidak dapat dibuat: (.+)$"), r"Could not create the output folder: \1"),
    (re.compile(r"^Folder keluaran bukan folder: (.+)$"), r"The output path is not a folder: \1"),
    (re.compile(r"^Folder keluaran tidak dapat ditulis: (.+)$"), r"The output folder is not writable: \1"),
    (re.compile(r"^Pola nama berkas tidak valid: (.+)$"), r"Invalid filename pattern: \1"),
    (re.compile(r"^Pola nama berkas tidak dapat dirender: (.+)$"), r"Could not render the filename pattern: \1"),
    (re.compile(r"^Mode pengambilan tidak dikenal: (.+)\.$"), r"Unknown capture mode: \1."),
    (re.compile(r"^Format keluaran tidak dikenal: (.+)\.$"), r"Unknown output format: \1."),
    (re.compile(r"^Pola nama berkas memakai placeholder yang tidak dikenal: (.+)\. Gunakan \{stem\}, \{index\}, \{time\}, dan \{ext\}\.$"), r"Unknown filename placeholder(s): \1. Use {stem}, {index}, {time}, and {ext}."),
    (re.compile(r"^Hasil tidak dapat disimpan ke (.+)\.$"), r"Could not save the result to \1."),
    (re.compile(r"^Ekstensi keluaran tidak didukung: (.+)\.$"), r"Unsupported output extension: \1."),
    (re.compile(r"^Durasi video ini ([\d.,]+) detik; turunkan waktu mulai\.$"), r"This video is \1 seconds long; lower the start time."),
    (re.compile(r"^Jumlah frame terlalu banyak \(([\d.,]+)\)\. Batas aman ([\d.,]+)\.$"), r"Too many frames requested (\1). The safe limit is \2."),
    (re.compile(r"^Interval terlalu rapat: akan menghasilkan ([\d.,]+) frame \(batas ([\d.,]+)\)\.$"), r"The interval is too small: it would produce \1 frames (limit \2)."),
    (re.compile(r"^ffmpeg berhenti dengan kode (\d+)\.$"), r"ffmpeg exited with code \1."),
    (re.compile(r"^Hanya ([\d.,]+) dari ([\d.,]+) frame yang berhasil dibuat\.$"), r"Only \1 of \2 frames were created successfully."),
    (re.compile(r"^Hanya ([\d.,]+) dari ([\d.,]+) frame yang berhasil dibaca\.$"), r"Only \1 of \2 frames were read successfully."),
    (re.compile(r"^OpenCV tidak dapat membuka (.+)\.$"), r"OpenCV could not open \1."),
    (re.compile(r"^Hasil tidak dapat disimpan: (.+)$"), r"Could not save the result: \1"),
    (re.compile(r"^Gambar tidak dapat dikodekan sebagai (.+)\.$"), r"The image could not be encoded as \1."),
    (re.compile(r"^Folder hasil tidak lagi tersedia:\n(.+)$", re.DOTALL), r"The results folder is no longer available:\n\1"),
)


def normalize_language(value: object) -> str:
    """Kembalikan kode bahasa yang dikenal; selain Inggris dianggap Indonesia."""

    text = str(value or "").strip().lower().replace("_", "-")
    if text == "en" or text.startswith("en-"):
        return "en"
    return DEFAULT_LANGUAGE


def format_count(value: int, lang: str | None = None) -> str:
    """Format bilangan bulat sesuai kebiasaan bahasa aktif."""

    text = f"{int(value):,}"
    return text if (lang or translator.language) == "en" else text.replace(",", ".")


class Translator(QObject):
    """Menyimpan bahasa aktif dan memberi tahu widget saat bahasa berubah."""

    languageChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._language = DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, value: object) -> None:
        language = normalize_language(value)
        if language == self._language:
            return
        self._language = language
        self.languageChanged.emit(language)

    def translate(self, source: str, **kwargs: object) -> str:
        entry: Translation | None = _ENGLISH.get(source) if self._language == "en" else source
        if entry is None:
            entry = source
        if isinstance(entry, tuple):
            count = kwargs.get("n", 0)
            try:
                numeric = int(count)
            except (TypeError, ValueError):
                numeric = 0
            entry = entry[0] if numeric == 1 else entry[1]
        if not kwargs:
            return entry
        values = dict(kwargs)
        if "n" in values:
            with suppress(TypeError, ValueError):
                values["n"] = format_count(int(values["n"]), self._language)
        try:
            return entry.format(**values)
        except (KeyError, IndexError, ValueError):
            # Teks dengan kurung kurawal literal tidak boleh membuat UI crash.
            return entry


translator = Translator()


def tr(source: str, **kwargs: object) -> str:
    """Terjemahkan ``source`` ke bahasa aktif dan isi placeholder-nya."""

    return translator.translate(source, **kwargs)


def language() -> str:
    return translator.language


def set_language(value: object) -> None:
    translator.set_language(value)


def translate_message(text: str) -> str:
    """Terjemahkan pesan galat/saran dari lapisan core bila memungkinkan.

    Pesan yang belum punya terjemahan dikembalikan apa adanya supaya detail
    teknis tetap bisa dibaca dan tidak ada informasi yang hilang.
    """

    if not text or translator.language != "en":
        return text
    exact = _ENGLISH.get(text)
    if isinstance(exact, str):
        return exact
    for pattern, replacement in _PATTERNS_EN:
        if pattern.search(text):
            return pattern.sub(replacement, text)
    return text


def translation_catalog() -> Mapping[str, Translation]:
    """Ekspos katalog hanya-baca untuk pengujian cakupan terjemahan."""

    return _ENGLISH


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "Translator",
    "format_count",
    "language",
    "normalize_language",
    "set_language",
    "tr",
    "translate_message",
    "translation_catalog",
    "translator",
]
