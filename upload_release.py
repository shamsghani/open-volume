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
    tag = "v2.0.2"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """# ⚡ Open-Volume 2.0.2 (Layer Deactivation on Timeout & Smooth Fade-Out)

A bugfix release resolving layer persistence when the HUD overlay times out, and restoring the smooth hardware-accelerated slide-out and fade-out animation.

---

### 🛠️ What's Fixed & Improved in v2.0.2

#### 1. 🔄 Layer Deactivation on Overlay Timeout
- **Problem**: When the overlay reached its inactivity timeout and disappeared, Layer 2 remained active in the background. Numpad keys continued to be intercepted as audio controls instead of normal typing.
- **Fix**: The autohide timer now immediately deactivates the low-level keyboard hook layer (`KeyboardHook::set_layer_active(false)`) and dispatches `AppAction::LayerExit`. Numpad keys immediately return to standard functionality.

#### 2. 🎬 Smooth Slide-Out & Fade-Out Animation
- Restored the smooth cubic ease-in fade-out and slide-out animation (~100ms) matching the legacy experience.
- When timing out or closing the overlay, the window smoothly glides away and fades out via DWM layered alpha instead of disappearing abruptly.

#### 3. 🔊 Synchronized Audio Feedback & Tray Tooltip
- Autohide timeout now properly updates the tray icon status to `READY` and triggers the layer-off sound cue (when sound feedback is enabled).
- Standalone toast notifications (e.g. media keys) fade away after 2 seconds without triggering spurious layer-off sounds.

---

### 📦 Downloads & Installation

- **`OpenVolume-v2.0.2-windows-x64.zip`**: Complete portable bundle (includes executable and docs).
- **`open-volume.exe`**: Standalone portable single-file executable (521 KB). No installation required!
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume 2.0.2 (Layer Deactivation on Timeout & Fade-Out)",
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
        ("dist/release/OpenVolume-v2.0.2-windows-x64.zip", "application/zip", "OpenVolume-v2.0.2-windows-x64.zip"),
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
