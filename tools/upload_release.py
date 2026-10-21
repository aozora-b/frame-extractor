import os
import sys
import subprocess
import json
import urllib.request
import urllib.error

def get_git_token():
    p = subprocess.Popen(
        ['git', 'credential', 'fill'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, _ = p.communicate('protocol=https\nhost=github.com\n\n')
    creds = dict(line.split('=', 1) for line in out.strip().splitlines() if '=' in line)
    return creds.get('password')

def main():
    token = get_git_token()
    if not token:
        print("ERROR: Token GitHub tidak ditemukan dari git-credential.")
        sys.exit(1)

    repo = "aozora-b/-frame-extractor"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Uploader"
    }

    # 1. Cek atau Buat Release v1.0.0
    releases_url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(releases_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            releases = json.loads(resp.read().decode())
    except Exception as e:
        releases = []

    release = next((r for r in releases if r.get("tag_name") == "v1.0.0"), None)
    if not release:
        print("Membuat Release v1.0.0 baru...")
        create_payload = {
            "tag_name": "v1.0.0",
            "target_commitish": "main",
            "name": "Frame Extractor v1.0.0 (Windows x64)",
            "body": (
                "## Rilis Perdana — Frame Extractor 1.0.0\n\n"
                "### Artefak Rilis Windows x64\n"
                "- `frame-extractor-v1.0.0-windows-x64.zip` (Onedir)\n"
                "- `frame-extractor-v1.0.0-windows-x64-onefile.zip` (Portable Onefile)\n"
                "- `SHA256SUMS.txt`\n\n"
                "### Verifikasi SHA-256\n"
                "```text\n"
                "b1757b3e38765fe91849ea90521f751de684188876e985c2b81dcf47d2d833b6  frame-extractor-v1.0.0-windows-x64.zip\n"
                "2e850d0c39646e11e8e7244869f48bcc030cba9b6d09f70e99f3dcee44755ee5  frame-extractor-v1.0.0-windows-x64-onefile.zip\n"
                "```\n"
            ),
            "draft": False,
            "prerelease": False
        }
        create_req = urllib.request.Request(
            releases_url,
            data=json.dumps(create_payload).encode(),
            headers={**headers, "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(create_req) as resp:
            release = json.loads(resp.read().decode())
        print(f"Release v1.0.0 berhasil dibuat: {release.get('html_url')}")
    else:
        print(f"Release v1.0.0 sudah ada: {release.get('html_url')}")

    upload_url_template = release["upload_url"].split("{")[0]
    existing_assets = {a["name"]: a["id"] for a in release.get("assets", [])}

    dist_dir = r"C:\Users\Stelle\projects\frame-extractor\dist-release"
    files_to_upload = [
        "SHA256SUMS.txt",
        "frame-extractor-v1.0.0-windows-x64-onefile.zip",
        "frame-extractor-v1.0.0-windows-x64.zip"
    ]

    for fname in files_to_upload:
        fpath = os.path.join(dist_dir, fname)
        if not os.path.exists(fpath):
            print(f"File {fname} tidak ditemukan di {dist_dir}, lewati.")
            continue

        if fname in existing_assets:
            print(f"Asset {fname} sudah terupload sebelumnya (id: {existing_assets[fname]}), lewati.")
            continue

        fsize = os.path.getsize(fpath)
        print(f"Mengunggah {fname} ({fsize / (1024*1024):.2f} MB)... Harap tunggu sebentar.")

        content_type = "text/plain" if fname.endswith(".txt") else "application/zip"
        target_upload_url = f"{upload_url_template}?name={fname}"

        with open(fpath, "rb") as f:
            data = f.read()

        upload_req = urllib.request.Request(
            target_upload_url,
            data=data,
            headers={
                **headers,
                "Content-Type": content_type,
                "Content-Length": str(len(data))
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(upload_req) as resp:
                asset_info = json.loads(resp.read().decode())
                print(f"Berhasil mengunggah {fname} -> {asset_info.get('browser_download_url')}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"Gagal mengunggah {fname}: HTTP {e.code} - {err_body}")

    print("\nSemua proses upload rilis selesai!")
    print(f"Halaman Rilis: {release.get('html_url')}")

if __name__ == "__main__":
    main()
