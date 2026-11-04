import ctypes
import sys
import os

# --- Single Instance Enforcement via Named Mutex ---
MUTEX_NAME = "Local\\MountainEverest60_NumpadAudioLayer_SingleInstance"
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
h_mutex = None

def check_single_instance():
    global h_mutex
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
from settings_ui import SettingsWindow

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
        curve_enabled = self.config.get("volume", {}).get("perceptual_curve", True)
        pinned = self.config.get("pinned_apps", ["Discord", "Spotify", "Google Chrome"])
        self.mixer = AudioMixer(perceptual_curve=curve_enabled, pinned_apps=pinned)

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
            "on_select_index": self._dispatch_select_index,
            "on_toggle_mic_mute": self._dispatch_toggle_mic_mute,
            "on_play_pause": self._dispatch_play_pause,
            "on_next_track": self._dispatch_next_track,
            "on_prev_track": self._dispatch_prev_track
        }
        self.hook = NumpadLayerHook(self.config, callbacks)

        # Settings & Macro UI
        self.settings_win = SettingsWindow(
            self.root,
            self.config_mgr,
            on_save_callback=self._on_settings_saved,
            on_preview_callback=self._on_settings_preview
        )

        # Tray Icon
        self.tray_icon = None
        self._setup_tray()

        # Sync startup state with config
        import startup_manager
        startup_manager.sync_with_config(self.config)

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

    def _refresh_overlay_hud(self):
        apps = self.mixer.get_apps()
        idx = self.mixer.get_selected_index()
        mic = self.mixer.get_microphone_info()
        dev = self.mixer.get_current_playback_device_name()
        peaks = self.mixer.get_peak_levels()
        self.overlay.update_data(apps, idx, mic_info=mic, device_name=dev, peak_levels=peaks)

    def _handle_layer_enter(self):
        print("[App] _handle_layer_enter -> Displaying HUD overlay!")
        self.mixer.refresh()
        if self.config.get("behavior", {}).get("follow_focus", True):
            self.mixer.auto_select_foreground_app()
        self._refresh_overlay_hud()
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
        self._refresh_overlay_hud()

    def _dispatch_volume_down(self, step):
        self.action_queue.put((self._handle_volume_down, (step,)))

    def _handle_volume_down(self, step):
        new_vol = self.mixer.adjust_volume(-step)
        app = self.mixer.get_selected_app()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Vol DOWN (-{step}%) -> {name}: {new_vol}%")
        self._refresh_overlay_hud()

    def _dispatch_select_next(self):
        self.action_queue.put((self._handle_select_next, ()))

    def _handle_select_next(self):
        app = self.mixer.select_next()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Cycle NEXT -> {name}")
        self._refresh_overlay_hud()

    def _dispatch_select_prev(self):
        self.action_queue.put((self._handle_select_prev, ()))

    def _handle_select_prev(self):
        app = self.mixer.select_prev()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Cycle PREV -> {name}")
        self._refresh_overlay_hud()

    def _dispatch_toggle_mute(self):
        self.action_queue.put((self._handle_toggle_mute, ()))

    def _handle_toggle_mute(self):
        muted = self.mixer.toggle_mute()
        app = self.mixer.get_selected_app()
        name = app['name'] if app else 'Unknown'
        print(f"[App] Mute Toggle -> {name}: {'MUTED' if muted else 'UNMUTED'}")
        self._refresh_overlay_hud()

    def _dispatch_select_index(self, idx):
        self.action_queue.put((self._handle_select_index, (idx,)))

    def _handle_select_index(self, idx):
        app = self.mixer.select_index(idx)
        name = app['name'] if app else 'Unknown'
        print(f"[App] Select Index [{idx}] -> {name}")
        self._refresh_overlay_hud()

    def _dispatch_toggle_mic_mute(self):
        self.action_queue.put((self._handle_toggle_mic_mute, ()))

    def _handle_toggle_mic_mute(self):
        new_mute = self.mixer.toggle_microphone_mute()
        msg = "Microphone MUTED" if new_mute else "Microphone LIVE"
        icon = "🎙️"
        print(f"[App] Mic Mute -> {msg}")
        self.overlay.show_toast(msg, icon=icon)
        self._refresh_overlay_hud()
        self._update_tray_state()

    def _dispatch_play_pause(self):
        self.action_queue.put((self._handle_play_pause, ()))

    def _handle_play_pause(self):
        user32.keybd_event(0xB3, 0, 0, 0)
        user32.keybd_event(0xB3, 0, 2, 0)
        print("[App] Media -> Play / Pause")
        self.overlay.show_toast("Play / Pause", icon="⏯")

    def _dispatch_next_track(self):
        self.action_queue.put((self._handle_next_track, ()))

    def _handle_next_track(self):
        user32.keybd_event(0xB0, 0, 0, 0)
        user32.keybd_event(0xB0, 0, 2, 0)
        print("[App] Media -> Next Track")
        self.overlay.show_toast("Next Track", icon="⏭")

    def _dispatch_prev_track(self):
        self.action_queue.put((self._handle_prev_track, ()))

    def _handle_prev_track(self):
        user32.keybd_event(0xB1, 0, 0, 0)
        user32.keybd_event(0xB1, 0, 2, 0)
        print("[App] Media -> Previous Track")
        self.overlay.show_toast("Previous Track", icon="⏮")

    def _on_timeout(self):
        self.hook.set_layer_active(False)

    # --- System Tray Setup ---

    def _create_tray_image(self, active=False):
        # 1. Try loading vibrant assets/icon.png
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            try:
                base = Image.open(icon_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                if active:
                    draw = ImageDraw.Draw(base)
                    accent = self.config.get("appearance", {}).get("accent_color", "#00E5A3")
                    # Vibrant active indicator badge
                    draw.ellipse((42, 42, 60, 60), fill=accent, outline="#FFFFFF", width=2)
                return base
            except Exception:
                pass

        # 2. Crisp, high-contrast fallback drawn icon (clean on both dark & light taskbars)
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        accent_col = self.config.get("appearance", {}).get("accent_color", "#00E5A3")
        color = accent_col if active else "#E0E0E0"
        fill_col = "#242838" if active else "#1A1B24"

        draw.ellipse((4, 4, 60, 60), fill=fill_col, outline=color, width=3)
        draw.rectangle((16, 24, 26, 40), fill=color)
        draw.polygon([(26, 24), (40, 14), (40, 50), (26, 40)], fill=color)
        if active:
            draw.arc((38, 20, 56, 44), start=-60, end=60, fill=color, width=3)
        return img

    def _setup_tray(self):
        def _is_pos(p):
            return lambda item: self.config.get("appearance", {}).get("position", "bottom-right") == p

        def _set_pos(p):
            def _action(icon, item):
                self.action_queue.put((self._change_position, (p,)))
            return _action

        def _is_anim(item):
            return self.config.get("appearance", {}).get("animation_enabled", True)

        def _toggle_anim(icon, item):
            self.action_queue.put((self._toggle_animation, ()))

        def _is_startup(item):
            import startup_manager
            return startup_manager.is_startup_enabled()

        def _toggle_startup(icon, item):
            self.action_queue.put((self._toggle_startup_action, ()))

        import theme_manager

        def _is_theme(tid):
            return lambda item: self.config.get("appearance", {}).get("theme", "cyberpunk") == tid

        def _set_theme(tid):
            def handler(icon, item):
                self.action_queue.put((self._apply_theme_action, (tid,)))
            return handler

        theme_items = [
            item(f"{t['emoji']} {t['name']}", _set_theme(t["id"]), checked=_is_theme(t["id"]), radio=True)
            for t in theme_manager.list_themes()
        ]
        themes_menu = pystray.Menu(*theme_items)

        position_menu = pystray.Menu(
            item("Top Left", _set_pos("top-left"), checked=_is_pos("top-left"), radio=True),
            item("Top Center", _set_pos("top-center"), checked=_is_pos("top-center"), radio=True),
            item("Top Right", _set_pos("top-right"), checked=_is_pos("top-right"), radio=True),
            pystray.Menu.SEPARATOR,
            item("Bottom Left", _set_pos("bottom-left"), checked=_is_pos("bottom-left"), radio=True),
            item("Bottom Center", _set_pos("bottom-center"), checked=_is_pos("bottom-center"), radio=True),
            item("Bottom Right", _set_pos("bottom-right"), checked=_is_pos("bottom-right"), radio=True)
        )

        # Profiles menu
        profiles = self.config.get("profiles", {})
        def _apply_prof(pkey):
            def handler(icon, item):
                self.action_queue.put((self._apply_profile_action, (pkey,)))
            return handler

        prof_items = [
            item(f"{p.get('emoji', '🎛️')} {p.get('name', k)}", _apply_prof(k))
            for k, p in profiles.items()
        ]
        profiles_menu = pystray.Menu(*prof_items)

        def _is_mic_muted(item):
            return self.mixer.get_microphone_info().get("muted", False)

        def _is_follow_focus(item):
            return self.config.get("behavior", {}).get("follow_focus", True)

        def _toggle_follow_focus(icon, item):
            self.action_queue.put((self._toggle_follow_focus_action, ()))

        def _is_curve(item):
            return self.config.get("volume", {}).get("perceptual_curve", True)

        def _toggle_curve(icon, item):
            self.action_queue.put((self._toggle_curve_action, ()))

        def _is_media(item):
            return self.config.get("behavior", {}).get("numpad_media_keys", True)

        def _toggle_media(icon, item):
            self.action_queue.put((self._toggle_media_action, ()))

        menu = pystray.Menu(
            item(lambda text: "Open Volume: " + ("ACTIVE" if self.hook.is_layer_active() else "READY"), None, enabled=False),
            item("Toggle HUD Layer", self._tray_toggle_layer),
            item("Mute Microphone", lambda icon, item: self._dispatch_toggle_mic_mute(), checked=_is_mic_muted),
            item("Settings & Keybindings...", self._tray_open_settings),
            pystray.Menu.SEPARATOR,
            item("Audio Profiles", profiles_menu),
            item("Theme Palette", themes_menu),
            item("Widget Position", position_menu),
            item("Follow Active Window", _toggle_follow_focus, checked=_is_follow_focus),
            item("Smooth dB Curve", _toggle_curve, checked=_is_curve),
            item("Numpad Media Keys", _toggle_media, checked=_is_media),
            item("Slide & Fade Animation", _toggle_anim, checked=_is_anim),
            item("Start with Windows", _toggle_startup, checked=_is_startup),
            item("Create Desktop Shortcut", self._tray_create_desktop_shortcut),
            item("Refresh Audio Sessions", self._tray_refresh_sessions),
            item("Open Config File", self._tray_open_config),
            pystray.Menu.SEPARATOR,
            item("Exit", self._tray_exit)
        )
        self.tray_icon = pystray.Icon(
            "NumpadAudioLayer",
            self._create_tray_image(False),
            "Open Volume - Audio Mixer & Macropad",
            menu=menu
        )

    def _apply_profile_action(self, profile_key: str):
        profiles = self.config.get("profiles", {})
        prof = profiles.get(profile_key)
        if prof:
            self.mixer.apply_profile(prof)
            name = prof.get("name", profile_key)
            emoji = prof.get("emoji", "🎛️")
            print(f"[App] Profile applied: {name}")
            self.overlay.show_toast(f"Profile: {name}", icon=emoji)
            self._refresh_overlay_hud()

    def _toggle_follow_focus_action(self):
        curr = self.config.get("behavior", {}).get("follow_focus", True)
        new_val = not curr
        self.config.setdefault("behavior", {})["follow_focus"] = new_val
        self.config_mgr.config = self.config
        self.config_mgr.save()
        self._update_tray_state()
        print(f"[App] Follow focus toggled -> {new_val}")

    def _toggle_curve_action(self):
        curr = self.config.get("volume", {}).get("perceptual_curve", True)
        new_val = not curr
        self.config.setdefault("volume", {})["perceptual_curve"] = new_val
        self.mixer.set_perceptual_curve(new_val)
        self.config_mgr.config = self.config
        self.config_mgr.save()
        self._update_tray_state()
        print(f"[App] Perceptual curve toggled -> {new_val}")

    def _toggle_media_action(self):
        curr = self.config.get("behavior", {}).get("numpad_media_keys", True)
        new_val = not curr
        self.config.setdefault("behavior", {})["numpad_media_keys"] = new_val
        self.config_mgr.config = self.config
        self.config_mgr.save()
        self.hook.update_config(self.config)
        self._update_tray_state()
        print(f"[App] Numpad media keys toggled -> {new_val}")

    def _tray_create_desktop_shortcut(self, icon, item):
        import startup_manager
        startup_manager.create_desktop_shortcut()

    def _tray_open_settings(self, icon, item):
        self.action_queue.put((self._show_settings, ()))

    def _show_settings(self):
        self.settings_win.show()

    def _apply_theme_action(self, theme_id: str):
        import theme_manager
        theme_manager.apply_theme_to_config(self.config, theme_id)
        self.config_mgr.config = self.config
        self.config_mgr.save()
        app_cfg = self.config.get("appearance", {})
        self.overlay.update_appearance(app_cfg)
        self._update_tray_state()
        print(f"[Tray] Theme switched to: {theme_id}")

    def _on_settings_saved(self, new_cfg):
        print("[App] Settings updated and applied dynamically.")
        self.config = new_cfg
        self.hook.update_config(new_cfg)
        app_cfg = new_cfg.get("appearance", {})
        self.overlay.update_appearance(app_cfg)
        self._update_tray_state()

    def _on_settings_preview(self, preview_cfg):
        print("[App] Triggering HUD preview from Settings...")
        app_cfg = preview_cfg.get("appearance", {})
        self.overlay.update_appearance(app_cfg)
        self.mixer.refresh()
        self._refresh_overlay_hud()
        self.overlay.show(animate=True)

    def _change_position(self, new_pos: str):
        print(f"[App] Changing widget position to: {new_pos}")
        if "appearance" not in self.config:
            self.config["appearance"] = {}
        self.config["appearance"]["position"] = new_pos
        self.config_mgr.save()
        self.overlay.set_position(new_pos)

        # Show brief preview with animation at the new spot
        self.mixer.refresh()
        self._refresh_overlay_hud()
        self.overlay.show(animate=True)

    def _toggle_animation(self):
        curr = self.config.get("appearance", {}).get("animation_enabled", True)
        new_val = not curr
        print(f"[App] Toggling animation -> {'ENABLED' if new_val else 'DISABLED'}")
        if "appearance" not in self.config:
            self.config["appearance"] = {}
        self.config["appearance"]["animation_enabled"] = new_val
        self.config_mgr.save()
        self.overlay.animation_enabled = new_val

    def _toggle_startup_action(self):
        import startup_manager
        curr = startup_manager.is_startup_enabled()
        new_val = not curr
        print(f"[App] Toggling Start with Windows -> {'ENABLED' if new_val else 'DISABLED'}")
        if startup_manager.set_startup_enabled(new_val):
            if "behavior" not in self.config:
                self.config["behavior"] = {}
            self.config["behavior"]["start_on_boot"] = new_val
            self.config_mgr.save()

    def _update_tray_state(self):
        if self.tray_icon:
            try:
                attach_to_default_desktop()
                is_active = self.hook.is_layer_active()
                self.tray_icon.icon = self._create_tray_image(is_active)
            except Exception as e:
                print(f"[Tray] Error updating icon state: {e}")

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

        # Start tray icon thread with explicit Default desktop setup callback
        def _tray_setup(icon):
            attach_to_default_desktop()
            icon.visible = True
            print("[Tray] Icon registered and visible on Default desktop.")

        def _run_tray():
            attach_to_default_desktop()
            try:
                self.tray_icon.run(setup=_tray_setup)
            except Exception as e:
                print(f"[Tray] Tray icon loop error: {e}")

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

        # Settings window CLI flag
        if "--settings" in sys.argv:
            self.root.after(200, self.settings_win.show)

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
    check_single_instance()
    app = MacropadAudioApp()
    app.run()
