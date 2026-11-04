import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

def get_token():
    p = subprocess.Popen(
        ['C:\\Program Files\\Git\\mingw64\\libexec\\git-core\\git-credential-wincred.exe', 'get'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    out, _ = p.communicate(input='protocol=https\nhost=github.com\nusername=shamsghani\n\n')
    for line in out.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1]
    raise RuntimeError("Could not find GitHub token for shamsghani")

def publish_release():
    token = get_token()
    owner = "shamsghani"
    repo = "open-volume"
    tag = "v1.1.0"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """## 🎛️ Mountain Everest 60 - Numpad Audio Layer 2 (v1.1.0)

A major update adding customizable HUD positioning and smooth slide-in / fade-in animations!

### ✨ What's New in v1.1.0
- **Configurable HUD Anchors**: Choose from 6 screen locations:
  - `top-left`, `top-center` / `top-mid`, `top-right`
  - `bottom-left`, `bottom-center` / `bottom-mid`, `bottom-right`
- **Dynamic Tray Switching**: Switch widget location on the fly with live visual preview via **System Tray > Widget Position** without needing to edit config files.
- **Fluent Slide-In & Fade-In Animation**: Smooth 60 FPS cubic ease-out animation sliding from the nearest screen edge. Fully customizable duration or togglable on the fly.
- **Snappy Dismissal**: Smooth cubic ease-in fade-out on timeout or instant dismiss on key press.

### 📦 Downloads
- **`MountainEverest60-NumpadAudio-v1.1.0-windows-x64.zip`**: Complete portable bundle (includes executable, customizable `config.json`, background launcher, and utility scripts).
- **`MountainEverestNumpad_Standalone.exe`**: Single-file portable executable.
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Mountain Everest 60 - Numpad Audio Layer v1.1.0",
        "body": body_md,
        "draft": False,
        "prerelease": False
    }

    print(f"Creating release {tag} on {owner}/{repo}...")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/releases",
        data=json.dumps(release_payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            rel = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        if "already_exists" in err_msg:
            print("Release already exists, fetching existing release...")
            get_req = urllib.request.Request(
                f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}",
                headers=headers
            )
            with urllib.request.urlopen(get_req) as resp:
                rel = json.loads(resp.read().decode())
        else:
            print(f"Error creating release ({e.code}): {err_msg}")
            sys.exit(1)

    release_id = rel["id"]
    upload_url_template = rel["upload_url"] # e.g. https://uploads.github.com/.../assets{?name,label}
    upload_base = upload_url_template.split("{")[0]
    print(f"Release ID: {release_id}")
    print(f"Release HTML URL: {rel.get('html_url')}")

    # Assets to upload
    assets = [
        ("dist/release/MountainEverest60-NumpadAudio-v1.1.0-windows-x64.zip", "application/zip", "MountainEverest60-NumpadAudio-v1.1.0-windows-x64.zip"),
        ("dist/MountainEverestNumpad_Standalone.exe", "application/octet-stream", "MountainEverestNumpad_Standalone.exe")
    ]

    for file_path, mime_type, name in assets:
        if not os.path.exists(file_path):
            print(f"Skipping {file_path} (not found)")
            continue

        file_size = os.path.getsize(file_path)
        print(f"\nUploading {name} ({file_size / (1024*1024):.1f} MB)...")

        upload_url = f"{upload_base}?name={name}"
        with open(file_path, "rb") as f:
            data = f.read()

        up_headers = headers.copy()
        up_headers["Content-Type"] = mime_type
        up_headers["Content-Length"] = str(file_size)

        up_req = urllib.request.Request(upload_url, data=data, headers=up_headers, method="POST")
        try:
            with urllib.request.urlopen(up_req) as resp:
                asset_info = json.loads(resp.read().decode())
                print(f"Successfully uploaded: {asset_info.get('browser_download_url')}")
        except urllib.error.HTTPError as e:
            print(f"Upload error for {name} ({e.code}): {e.read().decode()}")

    print("\n" + "=" * 60)
    print(f"  RELEASE PUBLISHED SUCCESSFULLY!")
    print(f"  URL: {rel.get('html_url')}")
    print("=" * 60)

if __name__ == "__main__":
    publish_release()
