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
    tag = "v2.1.1"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """# ⚡ Open-Volume 2.1.1 (Exclusion of AudioSrv & Self-Process)

A bugfix release resolving internal Windows audio service sessions and self-process clutter from the mixer list.

---

### 🛠️ What's Fixed in v2.1.1

#### 1. 🚫 Excluded Windows Audio Service (`@%SystemRoot%\\System32\\AudioSrv.Dll`)
- Windows Core Audio internally generates an unexpanded resource session string (`@%SystemRoot%\\System32\\AudioSrv.Dll,-202`) for system alert and notification sounds.
- Open-Volume now automatically identifies and excludes these internal Windows service sessions so only actual user applications are listed in the mixer.

#### 2. 🚫 Excluded Open-Volume Self-Process
- When Open-Volume plays audio feedback ("womp" enter, exit, volume steps), Windows creates an audio session for `open-volume.exe`.
- The mixer now automatically detects its own process ID (`std::process::id()`) and process name, preventing Open-Volume from appearing in its own audio list.

#### 3. ⚙️ User-Configurable Exclusion List
- Added `behavior.excluded_apps` to `config.json` (defaults: `["open-volume", "audiosrv"]`), allowing users to easily exclude any background processes or services from the HUD overlay.

---

### 📦 Downloads & Installation

- **`OpenVolume-v2.1.1-windows-x64.zip`**: Complete portable bundle (includes executable and docs).
- **`open-volume.exe`**: Standalone portable single-file executable (537 KB). No installation required!
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume 2.1.1 (Exclusion of AudioSrv & Self-Process)",
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
        ("dist/release/OpenVolume-v2.1.1-windows-x64.zip", "application/zip", "OpenVolume-v2.1.1-windows-x64.zip"),
        ("dist/release/open-volume.exe", "application/octet-stream", "open-volume.exe"),
        ("dist/release/OpenVolume-windows-x64.zip", "application/zip", "OpenVolume-windows-x64.zip")
    ]

    for file_path, mime_type, name in assets:
        if not os.path.exists(file_path):
            print(f"Skipping {file_path} (not found)")
            continue

        file_size = os.path.getsize(file_path)
        print(f"\nUploading {name} ({file_size / 1024:.1f} KB)...")

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
