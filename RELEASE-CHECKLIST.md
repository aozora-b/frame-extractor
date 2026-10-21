# Checklist Rilis — Frame Extractor 1.0.0

**Status keseluruhan: BELUM SIAP UNTUK RILIS PUBLIK.**

Build Windows lulus pengujian lokal. Build Linux dan macOS **belum pernah
dijalankan** karena lingkungan ini tidak memiliki mesin/runner tersebut dan
repositori GitHub belum tersedia. Biner juga belum ditandatangani. Karena itu
checklist ini **belum ditandatangani** dan T37/T38 belum selesai.

Tanggal: 21 Oktober 2026
Versi: `1.0.0`
Tag target: `v1.0.0` (belum dibuat)

## 1. Lingkungan build lokal

| Item | Nilai |
|---|---|
| Sistem | Windows 11 Enterprise N, versi 10.0.26200, x64 |
| Python | 3.12.10 |
| PySide6 / Qt | 6.12.0 |
| OpenCV | 5.0.0 (`opencv-python-headless`) |
| NumPy | 2.5.4 |
| ffmpeg | n8.1.3-18-g46d899d7a0, build BtbN LGPL *shared* |
| PyInstaller | 6.22.3 |

## 2. Matriks status

| Platform | Build | Aplikasi dibuka | Ekstraksi dari biner | Uji manual GUI | Ditandatangani |
|---|---|---|---|---|---|
| Windows x64 (`--onedir`) | LULUS | LULUS | LULUS (3 PNG) | BELUM | BELUM |
| Windows x64 (`--onefile`) | LULUS | LULUS | LULUS (3 PNG) | BELUM | BELUM |
| Linux x64 | BELUM DIUJI | BELUM DIUJI | BELUM DIUJI | BELUM DIUJI | BELUM |
| macOS arm64 | BELUM DIUJI | BELUM DIUJI | BELUM DIUJI | BELUM DIUJI | BELUM |

## 3. Bukti pengujian otomatis

- [x] `python -m pytest` — **111 passed** (7,37 detik), termasuk tes integrasi
      ffmpeg/OpenCV, pembatalan, CLI, GUI offscreen, kontras tema WCAG AA, dan
      pengalihan bahasa Indonesia/Inggris beserta persistensinya.
- [x] `python -m ruff check src tests tools` — tidak ada temuan.
- [x] Uji GUI sumber (`tools/gui_smoke.py` melalui pytest): 10 item galeri dan
      10 berkas PNG dari video uji 10 detik.
- [x] Simulasi tanpa ffmpeg (folder `third_party/ffmpeg/bin` dinonaktifkan):
      111 tes, 9 dilewati, 102 lulus; jalur OpenCV termasuk GUI tetap bekerja.
- [x] Konfigurasi `.github/workflows/release.yml` lolos parse YAML lokal.
- [ ] Workflow GitHub Actions benar-benar dijalankan pada Linux/macOS.
      **BELUM** — belum ada repositori/runner/kredensial GitHub.

## 4. Bukti build Windows

Perintah build:

```powershell
pyinstaller --noconfirm --clean --distpath dist --workpath build/work `
  build/frame_extractor.spec
pyinstaller --noconfirm --clean --distpath dist-onefile `
  --workpath build/work-onefile build/frame_extractor_onefile.spec
python build/package.py
```

| Artefak | Ukuran |
|---|---|
| `dist/Frame Extractor/` (`--onedir`) | 600.867.704 byte (573,0 MiB) |
| `dist-release/frame-extractor-windows-x64.zip` | 242.134.279 byte (242,1 MB) |
| `dist-onefile/Frame Extractor.exe` | 241.140.241 byte (230,0 MiB) |
| `dist-release/frame-extractor-windows-x64-onefile.zip` | 240.378.674 byte (240,4 MB) |

Checksum SHA-256 build lokal:

```text
081feb88049251c34f9f9381b182b54b7659679efd23ee62eb975e61aad798de  frame-extractor-windows-x64.zip
cd4cdbdc66712368e8b8919613227f7f46fe30e26d74ad68b0cc0079e67e1559  frame-extractor-windows-x64-onefile.zip
```

Checksum ini hanya berlaku untuk ZIP lokal tanggal 21 Oktober 2026. Build CI
akan menghasilkan checksum berbeda dan menulis `SHA256SUMS.txt` baru.

Bukti menjalankan biner:

- [x] `--onedir`: `--smoke-test` keluar dengan kode 0.
- [x] `--onedir`: `--self-test sample.mp4 --out ...` keluar 0 dan menghasilkan
      3 PNG.
- [x] `--onefile`: `--smoke-test` keluar dengan kode 0.
- [x] `--onefile`: `--self-test sample.mp4 --out ...` keluar 0 dan menghasilkan
      3 PNG.
- [x] Kedua ZIP diekstrak ke folder baru, lalu biner dijalankan dari hasil
      ekstrak: self-test dan smoke test sama-sama keluar 0.
- [x] Kedua biner dijalankan dari luar folder proyek dengan `PATH` hanya berisi
      `C:\Windows\System32` (tanpa Python/ffmpeg sistem): self-test menghasilkan
      3 PNG dan smoke test keluar 0.
- [x] Ikon tertanam pada kedua executable (32×32) dan metadata versi
      `FileVersion`/`ProductVersion` = `1.0.0`.
- [x] Ikon terlihat benar di taskbar Windows secara visual — diperiksa dari
      tangkapan layar desktop native pada 21 Oktober 2026; ikon aplikasi tampil
      di taskbar, bukan ikon Python.
- [ ] Dijalankan di mesin bersih tanpa Python terpasang oleh penguji manusia.
      **BELUM** — pengujian di atas memakai VM yang sama, meski `PATH` sudah
      dibatasi.

## 5. Smoke test manual per OS (T37)

### Windows x64

- [x] Jalankan dari hasil ekstrak ZIP, bukan dari folder build.
- [x] Buka jendela tanpa jendela konsol.
- [x] Ekstraksi mesin dari biner paket menghasilkan PNG.
- [ ] Buka satu video melalui GUI paket, tekan **Mulai**, lihat galeri.
      **BELUM** — jalur GUI diuji dari sumber, bukan dari biner paket.
- [x] Pembatalan mempertahankan hasil parsial (tes otomatis ffmpeg + OpenCV).
- [x] Video rusak menampilkan galat yang dapat dibaca (tes otomatis CLI/probe).
- [x] Folder keluaran tanpa izin tulis ditolak dengan galat (tes otomatis).
- [ ] Antrean batch 5 berkas diuji manual. **BELUM**.
- [ ] Seluruh alur diselesaikan hanya dengan keyboard (urutan Tab, fokus,
      pintasan). **BELUM** — implementasi ada, verifikasi manual penuh belum.
- [ ] Tujuh keadaan pada bagian 5.2 spesifikasi diuji manual satu per satu.
      **BELUM** — sebagian tercakup tes otomatis.
- [ ] SmartScreen/Defender di mesin bersih. **BELUM**.
- [ ] Biner ditandatangani code-signing. **BELUM**.

### Linux x64

- [ ] Workflow membangun `frame-extractor-linux-x64.tar.gz`. **BELUM DIUJI.**
- [ ] Jalankan di X11/Wayland nyata. **BELUM DIUJI.**
- [ ] `--self-test` dan `--smoke-test` pada biner hasil CI. **BELUM DIUJI.**
- [ ] Buka video, ekstrak, batalkan, video rusak, folder tanpa izin, batch 5.
      **BELUM DIUJI.**
- [ ] Tidak ada pustaka Qt/xcb yang hilang. **BELUM DIUJI.**
- [ ] Ditandatangani/diverifikasi. **BELUM.**

### macOS arm64

- [ ] Workflow membangun `frame-extractor-macos-arm64.zip`. **BELUM DIUJI.**
- [ ] Buka `Frame Extractor.app` (Gatekeeper, klik kanan > Open).
      **BELUM DIUJI.**
- [ ] `--self-test` dan `--smoke-test` pada biner hasil CI. **BELUM DIUJI.**
- [ ] Mesin OpenCV bekerja tanpa ffmpeg bawaan. **BELUM DIUJI.**
- [ ] Buka video, ekstrak, batalkan, video rusak, folder tanpa izin, batch 5.
      **BELUM DIUJI.**
- [ ] Ditandatangani dan di-notarize. **BELUM.**

## 6. Verifikasi unduhan

Dari folder yang berisi aset rilis:

```bash
sha256sum -c SHA256SUMS.txt
```

Windows PowerShell:

```powershell
Get-FileHash .\frame-extractor-windows-x64.zip -Algorithm SHA256
```

Bandingkan hasilnya dengan isi `SHA256SUMS.txt` pada halaman rilis.

## 7. Tanda tangan penguji

Checklist ini **belum ditandatangani**. Isi setelah ketiga OS diuji dari aset
rilis yang sama.

| Peran | Nama | Tanggal | Tanda tangan |
|---|---|---|---|
| Penguji Windows |  |  |  |
| Penguji Linux |  |  |  |
| Penguji macOS |  |  |  |
| Penanggung jawab rilis |  |  |  |

## 8. Tugas yang masih terblokir

| Tugas | Alasan | Yang dibutuhkan |
|---|---|---|
| T33 — workflow 3 OS | Workflow sudah ditulis, tetapi belum pernah dijalankan | Repositori GitHub + push/tag; log matrix hijau |
| T34 — draf rilis otomatis | Belum ada repositori, tag, atau kredensial | Tag `v1.0.0` dan izin `contents: write` |
| T37 — smoke test 3 OS | Hanya Windows yang tersedia di lingkungan ini | Mesin Linux x64 dan macOS arm64 |
| T38 — rilis v1.0.0 | Bergantung pada T33–T37 | Tiga aset + checksum + checklist bertanda tangan |

Catatan tambahan:

- URL repositori di `pyproject.toml` dan README masih berupa placeholder
  `github.com/example/frame-extractor`; ganti dengan URL repositori sebenarnya
  sebelum membuat tag.
- Riwayat Git dibuat setelah implementasi selesai. Commit dikelompokkan per
  fase, bukan satu commit per tugas T01–T38 seperti aturan spesifikasi.
- `third_party/ffmpeg/` tidak ikut di-commit; workflow mengunduhnya ulang.
  Build lokal memerlukan ffmpeg LGPL di folder tersebut.
