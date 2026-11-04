# Mountain Everest 60 - Numpad Audio Layer 2 (Macropad Controller)

A lightweight, high-performance background utility that turns the **Mountain Everest 60 modular numpad** into a dedicated **Layer 2 Audio Mixer & Macropad**.

With a simple hotkey, the numpad enters a secondary control layer and displays an elegant, system-wide HUD widget. In this mode, the numpad allows cycling through open audio applications (and Windows Master volume), adjusting individual app volumes with `+` and `-`, and instantly muting with `5` or `Enter`.

---

## ✨ Features

- **Instant Layer 2 Toggle**:
  - Press **`Ctrl + NumLock`** or **Double-tap `NumLock`** (within 400ms) to toggle Layer 2.
- **Dedicated Volume Controls**:
  - `+` (`Numpad +` or `+`): Increase volume (+5% default, +2% with Shift for fine tuning).
  - `-` (`Numpad -` or `-`): Decrease volume (-5% default, -2% with Shift).
- **App Navigation & Cycling**:
  - `8` or `4` or `/` or `▲`: Cycle to previous audio application.
  - `2` or `6` or `*` or `▼`: Cycle to next audio application.
  - `0` – `9`: Instantly jump directly to that app index in the list.
- **Mute / Unmute**:
  - `5` or `Numpad Enter`: Toggle mute for the currently selected application.
- **System-Wide Non-Activating HUD Overlay**:
  - Uses Windows `WS_EX_NOACTIVATE` so the overlay **never steals focus** from your full-screen game, browser, terminal, or coding environment.
  - Displays **System (Master Volume)** at the top, followed by all active audio sessions (Spotify, Discord, Chrome, Games, Media Players).
  - High-contrast graphical volume bars and live percentage badges.
- **Zero Input Leakage**:
  - While Layer 2 is active, numpad keystrokes are intercepted at the driver level (`WH_KEYBOARD_LL`) and consumed, preventing rogue numbers or math operators from typing into background documents.
  - Once Layer 2 exits, the numpad returns to 100% normal numeric typing.
- **Auto-Exit & Inactivity Dismiss**:
  - Single tap of `NumLock` or `Esc` immediately exits Layer 2.
  - Auto-hides after 6 seconds of inactivity (customizable in `config.json`).
- **System Tray Integration**:
  - Runs unobtrusively in the Windows taskbar system tray with a dynamic status icon and quick right-click menu.

---

## 🎮 Numpad Controls in Layer 2

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

You can edit `config.json` at any time to tweak behaviors, hotkeys, step sizes, and visual themes:

```json
{
  "hotkey": {
    "ctrl_numlock": true,
    "double_tap_numlock": true,
    "double_tap_max_interval_ms": 400
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

