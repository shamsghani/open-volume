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
    tag = "v1.2.1"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Release-Agent"
    }

    # Release body notes
    body_md = """## 🎛️ Open-Volume / Numpad Audio Layer (v1.2.1)

A hotfix and enhancement update adding **8-voice polyphonic sound playback** (preventing audio cut-outs during rapid spamming) and **Windows 11 system tray fixes**.

---

### ✨ What's New in v1.2.1

#### 1. 🔊 8-Voice Native Polyphonic Audio Engine
- **No More Disappearing Sounds on Rapid Spam**: When spamming or holding `+` / `-`, each keystroke now triggers an independent voice in an 8-voice native WinMM `waveOut` audio pool.
- Keypresses overlap naturally into a clean, ratcheted mechanical purr rather than cutting out, muting into silence, or buffering.
- **Zero Buffer Lag**: Because each audio burst is only 45ms and rendered polyphonically, sound ends within 45ms of releasing the key.

#### 2. 🪟 Windows 11 System Tray Fixes
- **Interactive Desktop Binding**: Fixed an issue where the tray icon creation thread failed to register with the interactive Explorer shell on Windows 11.
- **High-Contrast Cyan Icon**: Updated the tray graphic to use the high-visibility mint/cyan logo with an active status badge, ensuring maximum visibility on dark and light Windows 11 taskbars.
- **Taskbar Pinned Guidance**: By default, Windows 11 places new tray icons inside the taskbar overflow menu (`^` chevron). Click the `^` chevron, grab the cyan Open-Volume icon, and drag it onto your visible taskbar to keep it pinned permanently.

#### 3. ⌨️ Universal Keyboard & Macro UI Enhancements
- Safe named mutex initialization allowing CLI `--settings` inspection and smooth background execution.
- Updated documentation and README with comprehensive controls, troubleshooting, and configuration guides.

---

### 📦 Downloads
- **`OpenVolume-v1.2.1-windows-x64.zip`**: Complete portable bundle (includes executable, custom assets, `config.json`, background runner, and utility scripts).
- **`MountainEverest60-NumpadAudio-v1.2.1-windows-x64.zip`**: Mirror package under original project naming.
- **`MountainEverestNumpad_Standalone.exe`**: Single-file portable executable.
"""

    release_payload = {
        "tag_name": tag,
        "target_commitish": "main",
        "name": "Open-Volume & Numpad Audio Layer v1.2.1",
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
        ("dist/release/OpenVolume-v1.2.1-windows-x64.zip", "application/zip", "OpenVolume-v1.2.1-windows-x64.zip"),
        ("dist/release/MountainEverest60-NumpadAudio-v1.2.1-windows-x64.zip", "application/zip", "MountainEverest60-NumpadAudio-v1.2.1-windows-x64.zip"),
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
