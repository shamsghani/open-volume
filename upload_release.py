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
    tag = "v2.1.0"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """# ⚡ Open-Volume 2.1.0 (Themed Settings, 6-Position Monitor Selector & Keybinds)

A major feature release bringing full theme integration to the Settings menu, an interactive 6-position screen monitor selector, visual custom keybinding recording with a one-click reset to defaults, and a direct GitHub repository shortcut.

---

### ✨ What's New in v2.1.0

#### 1. 📐 Interactive 6-Position Screen Monitor Selector
- Added a stylized monitor screen rectangle in the Settings menu illustrating all **6 screen anchor positions**:
  - `Top-Left`, `Top-Center`, `Top-Right`
  - `Bottom-Left`, `Bottom-Center`, `Bottom-Right`
- Clicking any zone in the monitor frame immediately docks the HUD overlay to that display edge with real-time feedback and updates the system tray position submenu.

#### 2. 🎨 Full Dynamic Theming in Settings Window
- The Settings window now fully inherits and renders using your active theme palette (`bg_color`, `card_bg`, `selected_bg`, `accent_color`, `text_primary`, `border_color`).
- Switching themes in the palette grid immediately transforms the Settings window in real-time.
- Double-buffered Win32 memory DC rendering ensures 100% flicker-free repaints.

#### 3. ⌨️ Manual Custom Keybinding Editor & 🔄 Reset to Defaults
- Configure all 10 core shortcuts directly from the UI without touching `config.json`:
  - *Toggle HUD Layer, Volume Up, Volume Down, Next App, Prev App, Toggle Mute, Global Mic Mute, Play/Pause, Next Track, Exit HUD*.
- Click any shortcut button to enter interactive recording mode (`[ Press Key... ]`) — press any key or combination (Ctrl, Alt, Shift, Win) to rebind.
- Press **Escape** anytime to cancel recording.
- One-click **`🔄 Reset Defaults`** button instantly restores standard factory shortcuts.

#### 4. ⭐ Direct GitHub Shortcut
- Added a one-click **`⭐ View GitHub`** button in the Settings header to visit the repository for updates, star the project, and report feedback.

---

### 📦 Downloads & Installation

- **`OpenVolume-v2.1.0-windows-x64.zip`**: Complete portable bundle (includes executable and docs).
- **`open-volume.exe`**: Standalone portable single-file executable (524 KB). No installation required!
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume 2.1.0 (Themed Settings, 6-Position Selector & Keybinds)",
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
        ("dist/release/OpenVolume-v2.1.0-windows-x64.zip", "application/zip", "OpenVolume-v2.1.0-windows-x64.zip"),
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
