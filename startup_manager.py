import os
import sys
import tempfile
import subprocess

STARTUP_SHORTCUT_NAME = "OpenVolume.lnk"
DESKTOP_SHORTCUT_NAME = "Open Volume.lnk"
TASK_NAME = "OpenVolume"

def get_startup_dir() -> str:
    """Returns the Windows user Startup directory."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser(r"~\AppData\Roaming")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")

def get_startup_shortcut_path() -> str:
    """Returns the full path to OpenVolume.lnk in the Startup directory."""
    return os.path.join(get_startup_dir(), STARTUP_SHORTCUT_NAME)

# Alias for backward compatibility
get_shortcut_path = get_startup_shortcut_path

def get_desktop_dir() -> str:
    """Returns the Windows Desktop directory, resolving OneDrive / redirected folders if present."""
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:
            if os.path.isdir(buf.value):
                return buf.value
    except Exception:
        pass

    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
        if os.path.isdir(onedrive_desktop):
            return onedrive_desktop
        std_desktop = os.path.join(userprofile, "Desktop")
        if os.path.isdir(std_desktop):
            return std_desktop

    return os.path.expanduser(r"~\Desktop")

def get_desktop_shortcut_path() -> str:
    """Returns the full path to Open Volume.lnk on the user's Desktop."""
    return os.path.join(get_desktop_dir(), DESKTOP_SHORTCUT_NAME)

def _create_shortcut_lnk(dest_path: str, base_dir: str = None, description: str = "Open-Volume Audio Mixer") -> bool:
    """Creates a Windows .lnk shortcut file pointing to either the frozen EXE or the silent VBS launcher."""
    if base_dir is None:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        target_path = sys.executable
        arguments_vbs = '""'
        working_dir = os.path.dirname(sys.executable)
        icon_path = sys.executable
    else:
        # Running from Python source: use wscript.exe with run_background.vbs for 0-window silent launch
        vbs_launcher = os.path.join(base_dir, "run_background.vbs")
        target_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        arguments_vbs = f'Chr(34) & "{vbs_launcher}" & Chr(34)'
        working_dir = base_dir
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = target_path

    vbs_content = f'''Set w = CreateObject("WScript.Shell")
Set s = w.CreateShortcut("{dest_path}")
s.TargetPath = "{target_path}"
s.Arguments = {arguments_vbs}
s.WorkingDirectory = "{working_dir}"
s.IconLocation = "{icon_path}"
s.Description = "{description}"
s.Save
'''

    tmp_vbs = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False) as f:
            f.write(vbs_content)
            tmp_vbs = f.name

        cscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cscript.exe")
        res = subprocess.run([cscript, "//nologo", tmp_vbs], capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(dest_path):
            return True
        else:
            print(f"[Shortcut] Error creating shortcut {dest_path}: {res.stderr or res.stdout}")
            return False
    except Exception as e:
        print(f"[Shortcut] Exception creating shortcut {dest_path}: {e}")
        return False
    finally:
        if tmp_vbs and os.path.exists(tmp_vbs):
            try:
                os.remove(tmp_vbs)
            except Exception:
                pass

def is_startup_enabled() -> bool:
    """Checks whether startup is enabled via Task Scheduler (/rl highest) or Startup folder shortcut."""
    # 1. Check Task Scheduler
    try:
        res = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True)
        if res.returncode == 0 and TASK_NAME in res.stdout:
            return True
    except Exception:
        pass

    # 2. Check Startup folder shortcut
    return os.path.exists(get_startup_shortcut_path())

def set_startup_enabled(enable: bool, base_dir: str = None) -> bool:
    """Enables or disables Windows startup with elevated privileges (Task Scheduler /rl highest)."""
    if base_dir is None:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

    shortcut_path = get_startup_shortcut_path()

    if not enable:
        # Delete scheduled task
        try:
            subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, text=True)
        except Exception:
            pass

        # Delete shortcut
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
            except Exception as e:
                print(f"[Startup] Failed to remove shortcut: {e}")
                return False
        print(f"[Startup] Disabled startup.")
        return True

    # Enable startup:
    # 1. Try creating an elevated Task Scheduler task (/rl highest) for seamless zero-UAC boot launch
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        tr_target = f'"{sys.executable}"'
    else:
        vbs_launcher = os.path.join(base_dir, "run_background.vbs")
        wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        tr_target = f'"{wscript}" "{vbs_launcher}"'

    try:
        cmd = ["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr_target, "/sc", "onlogon", "/rl", "highest", "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[Startup] Created elevated Task Scheduler task: {TASK_NAME}")
            # Clean up old Startup folder shortcut if present
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception:
                    pass
            return True
    except Exception as e:
        print(f"[Startup] Note: Task Scheduler returned {e}, falling back to Startup shortcut.")

    # 2. Fallback to standard Startup folder shortcut
    res = _create_shortcut_lnk(shortcut_path, base_dir=base_dir, description="Open-Volume Audio Mixer Startup")
    if res:
        print(f"[Startup] Created startup shortcut: {shortcut_path}")
    return res

def is_desktop_shortcut_exists() -> bool:
    """Checks whether the desktop shortcut currently exists."""
    return os.path.exists(get_desktop_shortcut_path())

def create_desktop_shortcut(base_dir: str = None) -> bool:
    """Creates a desktop shortcut pointing to Open-Volume."""
    dest_path = get_desktop_shortcut_path()
    res = _create_shortcut_lnk(dest_path, base_dir=base_dir, description="Open-Volume Audio Mixer & Macropad")
    if res:
        print(f"[Desktop] Created desktop shortcut: {dest_path}")
    return res

def remove_desktop_shortcut() -> bool:
    """Removes the desktop shortcut."""
    path = get_desktop_shortcut_path()
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"[Desktop] Removed desktop shortcut: {path}")
            return True
        except Exception as e:
            print(f"[Desktop] Failed to remove shortcut: {e}")
            return False
    return True

def sync_with_config(config: dict, base_dir: str = None) -> bool:
    """Syncs the startup state with config.json behavior.start_on_boot."""
    behavior = config.get("behavior", {})
    desired = behavior.get("start_on_boot", False)
    current = is_startup_enabled()

    if desired != current:
        return set_startup_enabled(desired, base_dir=base_dir)
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage OpenVolume Windows shortcuts and startup")
    parser.add_argument("--enable", action="store_true", help="Enable startup on boot")
    parser.add_argument("--disable", action="store_true", help="Disable startup on boot")
    parser.add_argument("--desktop", action="store_true", help="Create desktop shortcut")
    parser.add_argument("--remove-desktop", action="store_true", help="Remove desktop shortcut")
    parser.add_argument("--status", action="store_true", help="Check shortcuts status")
    args = parser.parse_args()

    if args.enable:
        print("Startup enabled:", set_startup_enabled(True))
    elif args.disable:
        print("Startup disabled:", set_startup_enabled(False))
    elif args.desktop:
        print("Desktop shortcut created:", create_desktop_shortcut())
    elif args.remove_desktop:
        print("Desktop shortcut removed:", remove_desktop_shortcut())
    else:
        print("Startup currently enabled:", is_startup_enabled())
        print("Desktop shortcut exists:", is_desktop_shortcut_exists())
        print("Desktop path:", get_desktop_shortcut_path())
