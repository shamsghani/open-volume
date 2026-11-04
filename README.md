# Open-Volume / Mountain Everest Numpad Audio Layer 2

A lightweight, high-performance background utility that turns your **numpad or any keyboard** into a dedicated **Layer 2 Audio Mixer & Macropad**.

With a simple hotkey, your keyboard enters a secondary control layer and displays an elegant, system-wide HUD widget. In this mode, you can cycle through open audio applications (and Windows Master volume), adjust individual app volumes with `+` and `-` (or arrow keys), and instantly mute with `5`, `M`, or `Enter`.

Compatible out-of-the-box with:
- **Mountain Everest 60 modular numpad**
- **All standard full-size keyboards with a numpad**
- **Tenkeyless (TKL), 60%, 65%, 75%, and compact laptop keyboards** (via custom macro bindings)

---

## ✨ Features

- **Instant Layer 2 Toggle**:
  - Full-size / Numpad: Press **`Ctrl + NumLock`**, **Double-tap `NumLock`**, or **`Ctrl + Numpad *`**.
  - TKL / Laptop / Custom: Press **`Ctrl + Alt + V`** (fully rebindable).
- **Dedicated Volume Controls**:
  - `+` (`Numpad +` or `Up Arrow`): Increase volume (+5% default, +2% with Shift for fine tuning).
  - `-` (`Numpad -` or `Down Arrow`): Decrease volume (-5% default, -2% with Shift).
- **App Navigation & Cycling**:
  - `8` / `4` / `/` / `Left Arrow`: Cycle to previous audio application.
  - `2` / `6` / `*` / `Right Arrow`: Cycle to next audio application.
  - `0` – `9`: Instantly jump directly to that app index in the list.
- **Mute / Unmute**:
  - `5`, `M`, or `Numpad Enter`: Toggle mute for the currently selected application.
- **Warm "Bump Womp" Micro-Interactions (Polyphonic Sound Engine)**:
  - Rich, smooth pre-synthesized audio feedback with zero latency or buffering.
  - Powered by an 8-voice native WinMM `waveOut` polyphony pool so that rapid spamming and key holding overlap naturally into a clean, ratcheted mechanical purr rather than cutting out or going silent.
- **Settings & Macro Keybinding UI**:
  - Visual dark-themed configuration dashboard with interactive key combination recorder, screen anchor selector, accent color picker, and live HUD preview.
- **System-Wide Non-Activating HUD Overlay**:
  - Uses Windows `WS_EX_NOACTIVATE` so the overlay **never steals focus** from your full-screen game, browser, terminal, or coding environment.
  - Displays **System (Master Volume)** at the top, followed by all active audio sessions (Spotify, Discord, Chrome, Games, Media Players).
  - High-contrast graphical volume bars and live percentage badges.
- **Zero Input Leakage**:
  - While Layer 2 is active, numpad/macro keystrokes are intercepted at the driver level (`WH_KEYBOARD_LL`) and consumed, preventing rogue characters from typing into background documents.
  - Main keyboard Enter is preserved so background chats and editors never get disrupted.
- **Auto-Exit & Inactivity Dismiss**:
  - Single tap of `NumLock` or `Esc` immediately exits Layer 2.
  - Auto-hides after 6 seconds of inactivity (customizable in `config.json` or Settings).
- **System Tray Integration**:
  - Runs unobtrusively in the Windows taskbar system tray with a dynamic status icon and quick right-click menu.
  - **Windows 11 Tray Icon Location**: By default, Windows 11 automatically places new tray icons inside the taskbar overflow menu (`^` chevron next to the clock). Click the `^` chevron, find the cyan Open-Volume speaker icon, and drag it down directly onto your visible taskbar to keep it permanently pinned!

---

## 📦 Releases & Downloads

Pre-built standalone releases for Windows 10 & 11 (64-bit) are available on [GitHub Releases](https://github.com/shamsghani/open-volume/releases):
- **`OpenVolume-v1.2.1-windows-x64.zip`**: Complete portable bundle (includes executable, custom assets, `config.json`, background runner, and utility scripts).
- **`MountainEverestNumpad_Standalone.exe`**: Single-file portable executable.

---

## 🎮 Controls

### Default Numpad Controls (Full-Size & Modular Numpads)

```
┌──────┬──────┬──────┬──────┐
│NumLk │  /   │  *   │  -   │
│ EXIT │ PREV │ NEXT │VOL - │
├──────┼──────┼──────┼──────┤
│  7   │  8   │  9   │  +   │
│ APP7 │ PREV │ APP9 │      │
├──────┼──────┼──────┤VOL + │
│  4   │  5   │  6   │      │
│ PREV │ MUTE │ NEXT │      │
├──────┼──────┼──────┼──────┤
│  1   │  2   │  3   │ENTER │
│ APP1 │ NEXT │ APP3 │ MUTE │
├──────┴──────┼──────┤      │
│      0      │  .   │      │
│   SYSTEM    │ RESET│      │
└─────────────┴──────┴──────┘
```

| Key | Layer 2 Action | Normal Mode (Layer 1) |
| :--- | :--- | :--- |
| **`Ctrl + NumLock`** | Toggle Layer 2 ON/OFF | Toggle Num Lock |
| **Double-tap `NumLock`** | Toggle Layer 2 ON/OFF | Toggle Num Lock |
| **`Ctrl + Numpad *`** | Toggle Layer 2 ON/OFF | Type `*` |
| **`NumLock`** *(single tap)* | Exit Layer 2 (back to normal) | Toggle Num Lock |
| **`Escape`** | Exit Layer 2 | Escape |
| **`8`** / **`4`** / **`/`** | Select Previous Application | Type number / divide |
| **`2`** / **`6`** / **`*`** | Select Next Application | Type number / multiply |
| **`+`** (`Numpad +`) | **Volume Up** (+5% / +2% with Shift) | Type `+` |
| **`-`** (`Numpad -`) | **Volume Down** (-5% / -2% with Shift) | Type `-` |
| **`5`** / **`Numpad Enter`** | **Toggle Mute / Unmute** | Type 5 / Numpad Enter |
| **`Main Keyboard Enter`** | *Ignored by Layer 2 (Works normally)* | Normal Enter |
| **`0`** – **`9`** | Jump directly to Application # (`0` = System Master) | Type number |
| **`.`** | Reset volume to 100% | Type `.` |

### Default Custom Macros (TKL, Laptops, Compact Keyboards)

| Action | Default Shortcut | Custom Rebinding Available? |
| :--- | :--- | :--- |
| **Toggle Layer 2** | `Ctrl + Alt + V` | ✅ Yes (Interactive Recorder) |
| **Volume Up** | `Up Arrow` (`↑`) | ✅ Yes (Interactive Recorder) |
| **Volume Down** | `Down Arrow` (`↓`) | ✅ Yes (Interactive Recorder) |
| **Next App** | `Right Arrow` (`→`) | ✅ Yes (Interactive Recorder) |
| **Previous App** | `Left Arrow` (`←`) | ✅ Yes (Interactive Recorder) |
| **Toggle Mute** | `M` | ✅ Yes (Interactive Recorder) |
| **Exit Layer 2** | `Escape` | ✅ Yes (Interactive Recorder) |

---

## 🎛️ Settings & Macro Configuration UI

Launch the Settings UI at any time by:
1. Right-clicking the **Open-Volume System Tray Icon** > **Settings & Keybindings...**
2. Or running:
   ```cmd
   python main.py --settings
   ```
   *(or `MountainEverestNumpad.exe --settings`)*

From the Settings UI you can:
- Switch operating modes: **Hybrid** (both numpad and custom macros), **Numpad Only**, or **Custom Macros Only**.
- Rebind any action using the interactive **Record** button (simply press your desired key combination).
- Choose screen positioning using the interactive **3x3 Screen Anchor Grid**.
- Pick your accent color with instant live preview.
- Toggle and adjust slide & fade animations.

---

## 🚀 How to Run

### Option 1: Standard Launcher
Double-click `run.bat` in this folder:
```cmd
run.bat
```

### Option 2: Silent Background Mode (No Console Window)
Double-click `run_background.vbs`:
- Runs completely in the background.
- Access the app anytime via the System Tray icon in your Windows taskbar.

### Option 3: Stop Background Instances
Double-click `stop.bat` to gracefully shut down any running instances.

---

## ⚙️ Configuration (`config.json`)

You can edit `config.json` at any time to tweak behaviors, hotkeys, step sizes, and visual themes (or change widget position and animation directly from the System Tray menu or Settings UI):

```json
{
  "mode": "hybrid",
  "hotkey": {
    "ctrl_numlock": true,
    "double_tap_numlock": true,
    "double_tap_max_interval_ms": 400
  },
  "custom_bindings": {
    "toggle_layer": { "vk": 86, "ctrl": true, "alt": true, "shift": false, "win": false, "display": "Ctrl + Alt + V" },
    "volume_up": { "vk": 38, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "Up Arrow" },
    "volume_down": { "vk": 40, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "Down Arrow" },
    "next_app": { "vk": 39, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "Right Arrow" },
    "prev_app": { "vk": 37, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "Left Arrow" },
    "toggle_mute": { "vk": 77, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "M" },
    "exit_layer": { "vk": 27, "ctrl": false, "alt": false, "shift": false, "win": false, "display": "Escape" }
  },
  "volume": {
    "step_percent": 5,
    "fine_step_percent": 2,
    "sound_feedback": true
  },
  "behavior": {
    "auto_hide_seconds": 6,
    "cycle_wraparound": true
  },
  "appearance": {
    "position": "bottom-right",
    "animation_enabled": true,
    "animation_duration_ms": 180,
    "margin_x": 28,
    "margin_y": 60,
    "width": 360,
    "max_visible_apps": 6,
    "accent_color": "#00E5A3",
    "bg_color": "#121318",
    "card_bg": "#1A1B24",
    "selected_bg": "#242838",
    "text_primary": "#FFFFFF",
    "text_secondary": "#8E90A6"
  }
}
```

### 📍 Supported Widget Positions
- **`"bottom-right"`** (Default above taskbar)
- **`"bottom-center"`** / **`"bottom-mid"`**
- **`"bottom-left"`**
- **`"top-right"`**
- **`"top-center"`** / **`"top-mid"`**
- **`"top-left"`**
- **`"center"`**

### 🎬 Slide & Fade Animation
- Smooth 60 FPS cubic ease-out slide-in & fade-in when activated.
- Slides in smoothly from the nearest screen edge (e.g. rising from the bottom or dropping from the top).
- Snappy cubic ease-in fade-out on dismissal.
- Fully togglable via `"animation_enabled": true/false` or via the System Tray menu / Settings UI.

---

## 🛠️ Architecture & Requirements

- **Python 3.10+** (64-bit)
- Dependencies installed via `requirements.txt`:
  - `pycaw`: Windows Core Audio APIs (WASAPI per-application session control)
  - `comtypes`: Low-level COM interface bridging
  - `psutil`: Process enumeration and name resolution
  - `pystray`: Windows notification area / system tray integration
  - `pillow`: Dynamic tray icon rendering
  - Standard `ctypes`: High-speed Win32 `WH_KEYBOARD_LL` low-level input hook
