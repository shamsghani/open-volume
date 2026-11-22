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
    tag = "v2.0.1"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """# ⚡ Open-Volume 2.0.1 (Hotfix: Global Mic Mute & Tray Context Menu)

A patch release bringing critical fixes to the native Rust architecture, ensuring true global microphone muting across all input endpoints (including Discord) and resolving system tray context menu interactions.

---

### 🛠️ What's Fixed in v2.0.1

#### 1. 🎙️ True Global Microphone Mute
- Iterates and mutes **all active capture devices** simultaneously via WASAPI (`EnumAudioEndpoints(eCapture, DEVICE_STATE_ACTIVE)`).
- Resolves issues where communications apps like **Discord**, OBS, or Teams did not mute because they were bound to a specific hardware or virtual endpoint rather than the generic default console device.
- HUD overlay now clearly displays `"All Microphones MUTED"` / `"All Microphones LIVE"`.

#### 2. 🖱️ System Tray Right-Click Context Menu
- Fixed 16-bit message decoding under Windows `NOTIFYICON_VERSION_4`: extracts `LOWORD(lParam)` so right-click events (`WM_CONTEXTMENU`, `WM_RBUTTONUP`) properly trigger the context menu.
- Implemented standard Win32 menu dismissal: clicking anywhere outside the menu cleanly closes it without leaving focus trapped.
- Added smart cursor coordinate detection from `wParam` and `GetCursorPos` for centered and multi-monitor taskbars.
- Added 350ms atomic debounce preventing double-menu popups.

#### 3. 👆 System Tray Left-Click Action
- Left-clicking the tray icon now immediately toggles the HUD overlay on/off (`NIN_SELECT`, `WM_LBUTTONUP`).

#### 4. 🔄 Explorer Boot & Restart Auto-Recovery
- Registered `TaskbarCreated` window message with elevated UIPI message filter bypass (`MSGFLT_ADD`), allowing Explorer restarts to automatically recreate the tray icon even while running elevated.
- Added persistent 1-second auto-retry timer on boot to gracefully handle delayed Explorer initialization.

#### 5. ⚙️ Settings Window Focus Restoration
- Updated `ShowWindow` call to `SW_SHOWNORMAL`, guaranteeing the settings window restores and focuses even if previously minimized.

---

### 📦 Downloads & Installation

- **`OpenVolume-v2.0.1-windows-x64.zip`**: Complete portable bundle (includes executable and docs).
- **`open-volume.exe`**: Standalone portable single-file executable (521 KB). No installation required!
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume 2.0.1 (Global Mic Mute & Tray Fixes)",
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
        ("dist/release/OpenVolume-v2.0.1-windows-x64.zip", "application/zip", "OpenVolume-v2.0.1-windows-x64.zip"),
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
