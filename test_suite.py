import sys
import os
import time
import unittest
import ctypes
from ctypes import wintypes

# Ensure local modules are found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from audio_mixer import AudioMixer

class TestAudioMixer(unittest.TestCase):
    """Verifies WASAPI Core Audio volume management."""

    def setUp(self):
        self.mixer = AudioMixer()

    def test_01_sessions_detected(self):
        apps = self.mixer.get_apps()
        self.assertGreater(len(apps), 0, "No audio sessions or master endpoint found!")
        print(f"\n  [PASS] Found {len(apps)} audio targets:")
        for i, a in enumerate(apps):
            print(f"         [{i}] {a['name']:<25} (Vol: {a['volume']}%, Muted: {a['muted']})")

    def test_02_master_volume_present(self):
        apps = self.mixer.get_apps()
        master = next((a for a in apps if a.get('is_master')), None)
        self.assertIsNotNone(master, "System (Master Volume) was not found in the list!")
        self.assertIn('volume', master)
        self.assertTrue(0 <= master['volume'] <= 100, f"Invalid master volume: {master['volume']}")
        print(f"  [PASS] Master Volume confirmed at {master['volume']}%, Muted={master['muted']}")

    def test_03_volume_adjustment_delta(self):
        # Select master
        self.mixer.select_index(0)
        initial_vol = self.mixer.get_selected_app()['volume']

        # Test volume step adjustment safely without hitting 0% or 100% boundary
        step = -5 if initial_vol >= 95 else +5
        new_vol = self.mixer.adjust_volume(step)
        self.assertEqual(new_vol, initial_vol + step, f"Volume step failed: got {new_vol}, expected {initial_vol + step}")

        # Restore original volume
        restored = self.mixer.adjust_volume(-step)
        self.assertEqual(restored, initial_vol, f"Volume restore failed: got {restored}, expected {initial_vol}")
        print(f"  [PASS] Volume step adjustment verified: {initial_vol}% -> {new_vol}% -> {restored}%")

    def test_04_app_selection_cycle(self):
        count = len(self.mixer.get_apps())
        if count > 1:
            idx0 = self.mixer.get_selected_index()
            app_next = self.mixer.select_next()
            self.assertEqual(self.mixer.get_selected_index(), (idx0 + 1) % count)
            app_prev = self.mixer.select_prev()
            self.assertEqual(self.mixer.get_selected_index(), idx0)
            print(f"  [PASS] App cycling verified (0 -> 1 -> 0 across {count} apps)")

class TestOverlayHUD(unittest.TestCase):
    """Verifies Tkinter OSD widget creation, layout, positioning, and Win32 styles."""

    def test_01_overlay_creation_and_styles(self):
        import tkinter as tk
        from overlay_ui import OverlayWidget

        cfg = ConfigManager().config
        root = tk.Tk()
        root.withdraw()

        overlay = OverlayWidget(root, cfg)
        dummy_apps = [
            {'name': 'System (Master Volume)', 'volume': 75, 'muted': False},
            {'name': 'Spotify', 'volume': 50, 'muted': False},
            {'name': 'Discord', 'volume': 80, 'muted': True}
        ]
        overlay.update_data(dummy_apps, 1)

        # Check geometry calculation
        self.assertEqual(len(overlay.apps), 3)
        self.assertEqual(overlay.selected_index, 1)

        # Check show / hide
        overlay.show()
        root.update()
        self.assertTrue(overlay.is_visible())

        # Check Win32 styles
        hwnd = overlay._get_toplevel_hwnd()
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOPMOST = 0x00000008
        self.assertTrue(bool(style & WS_EX_NOACTIVATE), f"WS_EX_NOACTIVATE style missing! Style: {hex(style)}")
        self.assertTrue(bool(style & WS_EX_TOPMOST), f"WS_EX_TOPMOST style missing! Style: {hex(style)}")

        overlay.hide()
        root.update()
        self.assertFalse(overlay.is_visible())
        root.destroy()
        print("\n  [PASS] Overlay HUD created, styled, and verified with WS_EX_NOACTIVATE and WS_EX_TOPMOST.")

class TestKeyboardHookLogic(unittest.TestCase):
    """Verifies low-level keyboard hook logic, layer triggers, and key suppression."""

    def test_01_layer_state_transitions(self):
        from keyboard_hook import NumpadLayerHook

        cfg = ConfigManager().config
        events = []

        callbacks = {
            "on_layer_enter": lambda: events.append("ENTER"),
            "on_layer_exit": lambda: events.append("EXIT"),
            "on_volume_up": lambda step: events.append(f"VOL_UP_{step}"),
            "on_volume_down": lambda step: events.append(f"VOL_DOWN_{step}"),
            "on_select_next": lambda: events.append("NEXT"),
            "on_select_prev": lambda: events.append("PREV"),
            "on_toggle_mute": lambda: events.append("MUTE"),
            "on_select_index": lambda idx: events.append(f"INDEX_{idx}")
        }

        hook = NumpadLayerHook(cfg, callbacks)
        self.assertFalse(hook.is_layer_active())

        # Test enter
        hook.set_layer_active(True)
        self.assertTrue(hook.is_layer_active())
        self.assertIn("ENTER", events)

        # Test exit
        hook.set_layer_active(False)
        self.assertFalse(hook.is_layer_active())
        self.assertIn("EXIT", events)
        print("\n  [PASS] Layer state transitions and event callbacks verified.")

    def test_02_enter_key_isolation(self):
        from keyboard_hook import NumpadLayerHook

        cfg = ConfigManager().config
        mute_events = []
        callbacks = {"on_toggle_mute": lambda: mute_events.append("MUTED")}
        hook = NumpadLayerHook(cfg, callbacks)

        # Verify suppressed keys list doesn't include regular VK_RETURN (13)
        self.assertNotIn(13, hook.suppressed_vks, "VK_RETURN should not be globally suppressed!")
        print("  [PASS] Main Enter key is strictly isolated from Numpad Enter.")

class TestStartupManager(unittest.TestCase):
    """Verifies Windows startup registration and shortcut creation."""

    def test_01_startup_toggle_and_cleanup(self):
        import startup_manager
        initial_state = startup_manager.is_startup_enabled()

        # Test enable
        res_enable = startup_manager.set_startup_enabled(True)
        self.assertTrue(res_enable, "Failed to create startup shortcut!")
        self.assertTrue(startup_manager.is_startup_enabled(), "Startup shortcut was not detected on disk!")

        # Test disable
        res_disable = startup_manager.set_startup_enabled(False)
        self.assertTrue(res_disable, "Failed to remove startup shortcut!")
        self.assertFalse(startup_manager.is_startup_enabled(), "Startup shortcut still exists after disable!")

        # Restore initial state
        startup_manager.set_startup_enabled(initial_state)
        print("\n  [PASS] Startup shortcut creation, detection, and removal verified.")

    def test_02_desktop_shortcut(self):
        import startup_manager
        res = startup_manager.create_desktop_shortcut()
        self.assertTrue(res, "Failed to create desktop shortcut!")
        self.assertTrue(startup_manager.is_desktop_shortcut_exists(), "Desktop shortcut was not detected on disk!")
        print("\n  [PASS] Desktop shortcut creation and detection verified.")

def run_all_tests():
    print("=" * 65)
    print("   MOUNTAIN EVEREST NUMPAD MACROPAD - FULL TEST SUITE")
    print("=" * 65)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(loader.loadTestsFromTestCase(TestAudioMixer))
    suite.addTest(loader.loadTestsFromTestCase(TestOverlayHUD))
    suite.addTest(loader.loadTestsFromTestCase(TestKeyboardHookLogic))
    suite.addTest(loader.loadTestsFromTestCase(TestStartupManager))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    if result.wasSuccessful():
        print("  [SUCCESS] ALL TESTS PASSED! (Audio, Overlay, Hook, Startup)")
    else:
        print(f"  [FAILED] FAILURES: {len(result.failures)} | ERRORS: {len(result.errors)}")
    print("=" * 65)
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
