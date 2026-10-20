# Pemberitahuan pihak ketiga

Frame Extractor sendiri dilisensikan dengan **MIT** (lihat `LICENSE`). Rilis
biner menyertakan komponen pihak ketiga berikut. Teks lisensi lengkap ada di
folder `licenses/`.

## Qt for Python (PySide6), Qt 6, dan Shiboken6

- Versi: PySide6 6.12, Qt 6.12, Shiboken6 6.12.
- Lisensi: **GNU Lesser General Public License versi 3 (LGPLv3)**.
  Teks: `licenses/LGPL-3.0.txt` dan `licenses/GPL-3.0.txt`.
- Sumber: <https://code.qt.io/cgit/qt/> dan
  <https://code.qt.io/cgit/pyside/pyside-setup.git/>.
- Aplikasi menautkan Qt secara dinamis. Pada rilis `--onedir`, pengguna dapat
  mengganti berkas DLL/dylib Qt di folder aplikasi dengan versi Qt 6 yang
  kompatibel. Tidak ada perubahan pada kode Qt.
- PySide6 digunakan di bawah LGPLv3; tidak ada lisensi komersial Qt yang
  disertakan.

## ffmpeg dan ffprobe

- Versi: ffmpeg 8.1 (build BtbN, varian **LGPL**, tanpa x264/x265).
- Lisensi: **LGPL versi 2.1 atau lebih baru**. Teks:
  `licenses/ffmpeg-LGPL.txt` dan `licenses/LGPL-2.1.txt`.
- Sumber build: <https://github.com/BtbN/FFmpeg-Builds>.
  Sumber ffmpeg: <https://ffmpeg.org/download.html>.
- Rilis Windows menyertakan build *shared* LGPL beserta DLL yang diperlukan.
  Rilis Linux menyertakan build *static* LGPL. Berkas lisensi asli build juga
  disalin ke `ffmpeg/bin/FFMPEG-LICENSE.txt` pada paket rilis.
- ffmpeg/ffprobe dijalankan sebagai proses terpisah, bukan ditautkan ke
  executable aplikasi.

## OpenCV

- Versi: OpenCV 5.0 melalui paket `opencv-python-headless`.
- Lisensi: **Apache License 2.0**. Teks: `licenses/Apache-2.0.txt`.
- Sumber: <https://opencv.org/> dan
  <https://github.com/opencv/opencv-python>.
- Pembungkus `opencv-python-headless` memakai lisensi MIT; lihat berkas
  `LICENSE.txt` di paket tersebut.

## NumPy

- Lisensi: **BSD 3-Clause**. Teks: `licenses/NumPy-BSD-3-Clause.txt`.
- Sumber: <https://numpy.org/>.

## Python

- Versi: CPython 3.12.
- Lisensi: **Python Software Foundation License**. Teks:
  `licenses/Python-3.12.txt`.
- Sumber: <https://www.python.org/>.

## PyInstaller

- Bootloader PyInstaller memakai GPLv2 dengan **Bootloader Exception** yang
  mengizinkan distribusi biner aplikasi. Teks:
  `licenses/PyInstaller-bootloader.txt`.
- Sumber: <https://pyinstaller.org/>.

## Catatan distribusi

- Aplikasi berjalan tanpa koneksi internet.
- Tidak ada telemetri atau unggahan data.
- Jika Anda mendistribusikan ulang biner, sertakan `LICENSE`,
  `THIRD-PARTY-NOTICES.md`, dan folder `licenses/` bersama aplikasi.
