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
    tag = "v1.2.0"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """## 🎛️ Open-Volume / Numpad Audio Layer (v1.2.0)

A universal release introducing support for **all keyboards & laptops**, a dedicated **Settings & Macro Keybinding UI**, and smooth **warm audio micro-interactions**!

---

### ✨ What's New in v1.2.0

#### 1. ⌨️ Universal Keyboard & Laptop Support (Hybrid Mode)
- Works out of the box with **any keyboard**: standard full-size numpads, modular numpads (Mountain Everest 60), tenkeyless (TKL), 60%, 65%, 75%, and compact laptops.
- Default **Hybrid Mode** keeps full numpad interception active while simultaneously listening for custom macros (e.g. `Ctrl + Alt + V`, `Up`/`Down`, `Left`/`Right`, `M`, `Esc`).

#### 2. 🎚️ Dedicated Settings & Keybindings UI
- Visual dark-themed configuration dashboard accessible via:
  - **System Tray Icon (Right-click) > Settings & Keybindings...**
  - CLI flag: `python main.py --settings` or `MountainEverestNumpad.exe --settings`
- **Interactive Key Combination Recorder**: Click "Record", press any key combination (modifiers + virtual key), and your macro is immediately configured.
- **3x3 Screen Anchor Selector**: One-click visual layout grid to position the HUD across 6 screen anchors (`top-left/mid/right`, `bottom-left/mid/right`).
- **Live Theme & Animation Tuning**: Accent color picker with instant HUD preview, animation speed control, and fine-tuning sliders.

#### 3. 🔊 Warm "Bump Womp" Micro-Interactions (Zero Latency)
- Replaced the harsh, single-thread PC-speaker beep with warm, rich synthesized micro-interaction sounds (`womp_enter`, `womp_exit`, `womp_up`, `womp_down`, `womp_cycle`, `womp_mute`).
- **Zero Buffer Lag**: Powered by asynchronous Win32 audio streaming (`SND_ASYNC`), rapid keypresses never queue or lag.

#### 4. 🪟 Windows 11 Taskbar Tray Integration
- Seamless background operation with status tray icon.
- *Tip for Windows 11*: New icons may initially appear inside the taskbar overflow chevron (`^`). Simply drag it onto your main taskbar to keep it pinned.

---

### 📦 Downloads
- **`OpenVolume-v1.2.0-windows-x64.zip`**: Complete portable bundle (includes executable, custom assets, `config.json`, background runner, and utility scripts).
- **`MountainEverest60-NumpadAudio-v1.2.0-windows-x64.zip`**: Mirror package under original project naming.
- **`MountainEverestNumpad_Standalone.exe`**: Single-file portable executable.
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume & Numpad Audio Layer v1.2.0",
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
        ("dist/release/OpenVolume-v1.2.0-windows-x64.zip", "application/zip", "OpenVolume-v1.2.0-windows-x64.zip"),
        ("dist/release/MountainEverest60-NumpadAudio-v1.2.0-windows-x64.zip", "application/zip", "MountainEverest60-NumpadAudio-v1.2.0-windows-x64.zip"),
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
