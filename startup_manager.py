import os
import sys
import tempfile
import subprocess

SHORTCUT_NAME = "OpenVolume.lnk"

def get_startup_dir() -> str:
    """Returns the Windows user Startup directory."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser(r"~\AppData\Roaming")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")

def get_shortcut_path() -> str:
    """Returns the full path to OpenVolume.lnk in the Startup directory."""
    return os.path.join(get_startup_dir(), SHORTCUT_NAME)

def is_startup_enabled() -> bool:
    """Checks whether the startup shortcut currently exists."""
    return os.path.exists(get_shortcut_path())

def set_startup_enabled(enable: bool, base_dir: str = None) -> bool:
    """Enables or disables Windows startup by creating/removing the shortcut.
    
    Returns True if the operation succeeded, False otherwise.
    """
    shortcut_path = get_shortcut_path()

    if not enable:
        if os.path.exists(shortcut_path):
            try:
                os.remove(shortcut_path)
                print(f"[Startup] Removed startup shortcut: {shortcut_path}")
                return True
            except Exception as e:
                print(f"[Startup] Failed to remove shortcut: {e}")
                return False
        return True

    # Enable startup
    if base_dir is None:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

    os.makedirs(get_startup_dir(), exist_ok=True)

    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        target_path = sys.executable
        arguments_vbs = '""'
        working_dir = os.path.dirname(sys.executable)
        icon_path = sys.executable
    else:
        # Running from Python source: use wscript.exe with run_background.vbs for 0-window launch
        vbs_launcher = os.path.join(base_dir, "run_background.vbs")
        target_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        arguments_vbs = f'Chr(34) & "{vbs_launcher}" & Chr(34)'
        working_dir = base_dir
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = target_path

    # Create shortcut using VBScript
    vbs_content = f'''Set w = CreateObject("WScript.Shell")
Set s = w.CreateShortcut("{shortcut_path}")
s.TargetPath = "{target_path}"
s.Arguments = {arguments_vbs}
s.WorkingDirectory = "{working_dir}"
s.IconLocation = "{icon_path}"
s.Description = "Open-Volume Audio Mixer & Macropad"
s.Save
'''

    tmp_vbs = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False) as f:
            f.write(vbs_content)
            tmp_vbs = f.name

        cscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cscript.exe")
        res = subprocess.run([cscript, "//nologo", tmp_vbs], capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(shortcut_path):
            print(f"[Startup] Created startup shortcut: {shortcut_path}")
            return True
        else:
            print(f"[Startup] Error creating shortcut: {res.stderr or res.stdout}")
            return False
    except Exception as e:
        print(f"[Startup] Exception creating shortcut: {e}")
        return False
    finally:
        if tmp_vbs and os.path.exists(tmp_vbs):
            try:
                os.remove(tmp_vbs)
            except Exception:
                pass

def sync_with_config(config: dict, base_dir: str = None) -> bool:
    """Syncs the startup shortcut state with config.json behavior.start_on_boot."""
    behavior = config.get("behavior", {})
    desired = behavior.get("start_on_boot", False)
    current = is_startup_enabled()

    if desired != current:
        return set_startup_enabled(desired, base_dir=base_dir)
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage OpenVolume Windows startup")
    parser.add_argument("--enable", action="store_true", help="Enable startup on boot")
    parser.add_argument("--disable", action="store_true", help="Disable startup on boot")
    parser.add_argument("--status", action="store_true", help="Check startup status")
    args = parser.parse_args()

    if args.enable:
        success = set_startup_enabled(True)
        print("Startup enabled:", success)
    elif args.disable:
        success = set_startup_enabled(False)
        print("Startup disabled:", success)
    else:
        print("Startup currently enabled:", is_startup_enabled())
