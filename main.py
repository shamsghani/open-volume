import ctypes
import sys
import os

# --- Single Instance Enforcement via Named Mutex ---
MUTEX_NAME = "Local\\MountainEverest60_NumpadAudioLayer_SingleInstance"
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

h_mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    print("[App] Another instance is already running! Exiting duplicate process.")
    sys.exit(0)

# 1. Attach to interactive desktop FIRST before any GUI libraries load
try:
    hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)  # GENERIC_ALL
    if hdesk:
        user32.SetThreadDesktop(hdesk)
except Exception as e:
    print(f"[Desktop] Init error: {e}")

# 2. Enable Per-Monitor DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

import threading
import queue
import time
import tkinter as tk
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

from config_manager import ConfigManager
from audio_mixer import AudioMixer
from overlay_ui import OverlayWidget
from keyboard_hook import NumpadLayerHook

def attach_to_default_desktop():
    """Ensures GUI window connects to WinSta0\\Default."""
    try:
        user32 = ctypes.windll.user32
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception as e:
        print(f"[Desktop] Could not switch thread desktop: {e}")

class MacropadAudioApp:
    def __init__(self):
        attach_to_default_desktop()

        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.config
        self.mixer = AudioMixer()

        # Thread-safe event queue for decoupling hook thread from Tkinter GUI thread
        self.action_queue = queue.Queue()

        # Tkinter root
        self.root = tk.Tk()
        self.root.withdraw()

        # Start the queue polling loop in the Tkinter main thread
        self.root.after(25, self._poll_action_queue)

        # Overlay widget
        self.overlay = OverlayWidget(
            self.root,
            self.config,
            on_timeout_callback=self._on_timeout
        )

        # Hook callbacks
        callbacks = {
            "on_layer_enter": self._dispatch_layer_enter,
            "on_layer_exit": self._dispatch_layer_exit,
            "on_volume_up": self._dispatch_volume_up,
            "on_volume_down": self._dispatch_volume_down,
            "on_select_next": self._dispatch_select_next,
            "on_select_prev": self._dispatch_select_prev,
            "on_toggle_mute": self._dispatch_toggle_mute,
            "on_select_index": self._dispatch_select_index
        }
        self.hook = NumpadLayerHook(self.config, callbacks)

        # Tray Icon
        self.tray_icon = None
        self._setup_tray()

    def _poll_action_queue(self):
        """Continuously processes actions queued by the background keyboard hook thread."""
        try:
            while not self.action_queue.empty():
                func, args = self.action_queue.get_nowait()
                try:
                    func(*args)
                except Exception as e:
                    print(f"[App] Action error: {e}")
        finally:
            self.root.after(25, self._poll_action_queue)

    # --- Thread-Safe Callbacks (Dispatched via Action Queue to Main Thread) ---

    def _dispatch_layer_enter(self):
        self.action_queue.put((self._handle_layer_enter, ()))

    def _handle_layer_enter(self):
        print("[App] _handle_layer_enter -> Displaying HUD overlay!")
        self.mixer.refresh()
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())
        self.overlay.show()
        self._update_tray_state()

    def _dispatch_layer_exit(self):
        self.action_queue.put((self._handle_layer_exit, ()))

    def _handle_layer_exit(self):
        print("[App] _handle_layer_exit -> Hiding HUD overlay")
        self.overlay.hide()
        self._update_tray_state()

    def _dispatch_volume_up(self, step):
        self.action_queue.put((self._handle_volume_up, (step,)))

    def _handle_volume_up(self, step):
        new_vol = self.mixer.adjust_volume(+step)
        app = self.mixer.get_selected_app()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Vol UP (+{step}%) -> {name}: {new_vol}%")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _dispatch_volume_down(self, step):
        self.action_queue.put((self._handle_volume_down, (step,)))

    def _handle_volume_down(self, step):
        new_vol = self.mixer.adjust_volume(-step)
        app = self.mixer.get_selected_app()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Vol DOWN (-{step}%) -> {name}: {new_vol}%")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _dispatch_select_next(self):
        self.action_queue.put((self._handle_select_next, ()))

    def _handle_select_next(self):
        app = self.mixer.select_next()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Cycle NEXT -> {name}")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _dispatch_select_prev(self):
        self.action_queue.put((self._handle_select_prev, ()))

    def _handle_select_prev(self):
        app = self.mixer.select_prev()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Cycle PREV -> {name}")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _dispatch_toggle_mute(self):
        self.action_queue.put((self._handle_toggle_mute, ()))

    def _handle_toggle_mute(self):
        muted = self.mixer.toggle_mute()
        app = self.mixer.get_selected_app()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Mute Toggle -> {name}: {'MUTED' if muted else 'UNMUTED'}")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _dispatch_select_index(self, idx):
        self.action_queue.put((self._handle_select_index, (idx,)))

    def _handle_select_index(self, idx):
        app = self.mixer.select_index(idx)
        name = app['name'] if app else 'Unknown'
        print(f"[App] Select Index [{idx}] -> {name}")
        self.overlay.update_data(self.mixer.get_apps(), self.mixer.get_selected_index())

    def _on_timeout(self):
        self.hook.set_layer_active(False)

    # --- System Tray Setup ---

    def _create_tray_image(self, active=False):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        border_col = self.config.get("appearance", {}).get("accent_color", "#00E5A3") if active else "#8E90A6"
        fill_col = "#242838" if active else "#1A1B24"

        # Rounded circle background
        draw.ellipse((4, 4, 60, 60), fill=fill_col, outline=border_col, width=4)

        # Speaker symbol
        draw.rectangle((18, 24, 28, 40), fill=border_col)
        draw.polygon([(28, 24), (42, 14), (42, 50), (28, 40)], fill=border_col)
        if active:
            draw.arc((40, 20, 56, 44), start=-60, end=60, fill=border_col, width=3)
        return img

    def _setup_tray(self):
        menu = pystray.Menu(
            item(lambda text: "Numpad Audio Layer: " + ("ACTIVE" if self.hook.is_layer_active() else "READY"), None, enabled=False),
            item("Toggle Layer 2 (Ctrl+NumLock)", self._tray_toggle_layer),
            item("Refresh Audio Sessions", self._tray_refresh_sessions),
            item("Open Config File", self._tray_open_config),
            pystray.Menu.SEPARATOR,
            item("Exit", self._tray_exit)
        )
        self.tray_icon = pystray.Icon(
            "NumpadAudioLayer",
            self._create_tray_image(False),
            "Numpad Audio Layer Controller",
            menu=menu
        )

    def _update_tray_state(self):
        if self.tray_icon:
            is_active = self.hook.is_layer_active()
            self.tray_icon.icon = self._create_tray_image(is_active)

    def _tray_toggle_layer(self, icon, item):
        new_state = not self.hook.is_layer_active()
        self.hook.set_layer_active(new_state)

    def _tray_refresh_sessions(self, icon, item):
        self.root.after(0, lambda: self.mixer.refresh())

    def _tray_open_config(self, icon, item):
        cfg_path = os.path.abspath(self.config_mgr.config_path)
        os.system(f'notepad.exe "{cfg_path}"')

    def _tray_exit(self, icon, item):
        self.hook.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        # Start keyboard hook
        self.hook.start()

        # Start tray icon thread
        def _run_tray():
            attach_to_default_desktop()
            self.tray_icon.run()

        tray_thread = threading.Thread(target=_run_tray, daemon=True)
        tray_thread.start()

        print("\n" + "=" * 55)
        print("   Mountain Everest 60 - Numpad Audio Layer 2")
        print("=" * 55)
        print("  Status: Listening for Numpad Layer 2 hotkeys...")
        print("  Controls:")
        print("    [Ctrl + NumLock]  : Toggle Layer 2 ON/OFF")
        print("    [Double-tap NumLk]: Toggle Layer 2 ON/OFF")
        print("    [Ctrl + Numpad *] : Alternative Toggle")
        print("    [8] / [2] or [/][*]: Cycle Audio Apps")
        print("    [+] / [-]         : Adjust Selected Volume")
        print("    [5] / [Enter]     : Toggle Mute / Unmute")
        print("    [0 - 9]           : Jump Directly to App Index")
        print("    [NumLock] / [Esc] : Exit Layer 2")
        print("=" * 55 + "\n")

        # Test popup flag check
        if "--test-popup" in sys.argv:
            print("[Test] --test-popup triggered. Displaying overlay for 4 seconds...")
            def _trigger_test():
                time.sleep(0.5)
                self.hook.set_layer_active(True)
                time.sleep(3.5)
                self.hook.set_layer_active(False)
            threading.Thread(target=_trigger_test, daemon=True).start()

        # Tkinter Main Loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.hook.stop()
            if self.tray_icon:
                self.tray_icon.stop()

if __name__ == "__main__":
    app = MacropadAudioApp()
    app.run()
