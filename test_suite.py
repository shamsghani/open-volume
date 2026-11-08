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

    def test_05_perceptual_curve(self):
        # Linear mode
        self.mixer.set_perceptual_curve(False)
        self.assertAlmostEqual(self.mixer.percent_to_scalar(50), 0.5, places=2)
        self.assertEqual(self.mixer.scalar_to_percent(0.5), 50)

        # Perceptual mode
        self.mixer.set_perceptual_curve(True)
        scalar = self.mixer.percent_to_scalar(50)
        self.assertLess(scalar, 0.40)
        self.assertEqual(self.mixer.scalar_to_percent(scalar), 50)
        print("  [PASS] Perceptual logarithmic dB curve mapping verified.")

    def test_06_pinned_apps_ordering(self):
        from audio_mixer import AudioMixer
        mixer = AudioMixer(pinned_apps=["Spotify", "Discord"])
        apps = mixer.get_apps()
        if len(apps) >= 3:
            self.assertTrue(apps[0]['is_master'])
            names = [a['name'].lower() for a in apps[1:3]]
            self.assertTrue(any('spotify' in n or 'discord' in n for n in names))
            print("  [PASS] Pinned apps prioritized ordering verified.")

    def test_07_microphone_info(self):
        mic = self.mixer.get_microphone_info()
        self.assertIn('name', mic)
        self.assertIn('volume', mic)
        self.assertIn('muted', mic)
        print(f"  [PASS] Microphone query verified: {mic['name']} (Vol: {mic['volume']}%, Muted: {mic['muted']})")

    def test_08_audio_profiles(self):
        profile = {
            "name": "Test Profile",
            "master": 90,
            "apps": { "Discord": 80, "Spotify": 50 }
        }
        res = self.mixer.apply_profile(profile)
        self.assertTrue(res)
        print("  [PASS] Audio profile preset application verified.")

    def test_09_peak_metering(self):
        peaks = self.mixer.get_peak_levels()
        self.assertEqual(len(peaks), len(self.mixer.get_apps()))
        for p in peaks:
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)
        print(f"  [PASS] Live audio peak meters verified across {len(peaks)} sessions.")

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

    def test_02_live_peak_meter_loop_and_ballistics(self):
        import tkinter as tk
        from overlay_ui import OverlayWidget

        cfg = ConfigManager().config
        root = tk.Tk()
        root.withdraw()

        overlay = OverlayWidget(root, cfg)
        dummy_apps = [
            {'name': 'System (Master Volume)', 'volume': 75, 'muted': False},
            {'name': 'Spotify', 'volume': 60, 'muted': False}
        ]
        overlay.update_data(dummy_apps, 1)

        # Mock peak provider returning 0.70 for Spotify
        mock_peaks = [0.10, 0.70]
        overlay.set_peak_level_provider(lambda: mock_peaks)

        overlay.show()
        root.update()

        # Check that live meter loop started
        self.assertTrue(overlay.is_visible())
        self.assertIsNotNone(overlay.live_meter_timer)

        # Allow a few frames to process
        for _ in range(5):
            root.update()
            time.sleep(0.035)

        # Verify instant attack: smoothed_peak should have jumped to ~0.70
        self.assertAlmostEqual(overlay.smoothed_peak, 0.70, places=2)
        self.assertAlmostEqual(overlay.hold_peak, 0.70, places=2)

        # Now mock silence (peak drops to 0.0)
        mock_peaks = [0.0, 0.0]
        for _ in range(4):
            root.update()
            time.sleep(0.035)

        # Verify smooth exponential decay: should decay smoothly without immediately jumping to 0.0
        self.assertGreater(overlay.smoothed_peak, 0.0)
        self.assertLess(overlay.smoothed_peak, 0.70)

        # Verify hide cleanly cancels live meter timer
        overlay.hide()
        root.update()
        self.assertIsNone(overlay.live_meter_timer)
        root.destroy()
        print("  [PASS] Live VU meter real-time polling, instant attack, and exponential decay verified.")

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

    def test_03_media_and_mic_callbacks(self):
        from keyboard_hook import NumpadLayerHook
        cfg = ConfigManager().config
        fired = []
        callbacks = {
            "on_play_pause": lambda: fired.append("PLAY_PAUSE"),
            "on_next_track": lambda: fired.append("NEXT_TRACK"),
            "on_prev_track": lambda: fired.append("PREV_TRACK"),
            "on_toggle_mic_mute": lambda: fired.append("MIC_MUTE")
        }
        hook = NumpadLayerHook(cfg, callbacks)
        self.assertIn("on_play_pause", hook.callbacks)
        self.assertIn("on_next_track", hook.callbacks)
        self.assertIn("on_prev_track", hook.callbacks)
        self.assertIn("on_toggle_mic_mute", hook.callbacks)
        print("  [PASS] Media transport and microphone hook callbacks verified.")

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

class TestThemeManager(unittest.TestCase):
    """Verifies Theme System paletting, defaults, and config application."""

    def test_01_themes_definition(self):
        import theme_manager
        themes = theme_manager.list_themes()
        self.assertGreaterEqual(len(themes), 8)
        required_keys = [
            "id", "name", "accent_color", "bg_color", "card_bg",
            "selected_bg", "text_primary", "text_secondary",
            "border_color", "track_bg", "danger_color"
        ]
        for t in themes:
            for k in required_keys:
                self.assertIn(k, t, f"Theme {t.get('id')} missing key {k}")
                self.assertTrue(t[k], f"Theme {t.get('id')} has empty {k}")
        print(f"\n  [PASS] All {len(themes)} themes verified with complete color palettes.")

    def test_02_apply_theme_to_config(self):
        import theme_manager
        cfg = {"appearance": {}}
        theme_manager.apply_theme_to_config(cfg, "dracula")
        self.assertEqual(cfg["appearance"]["theme"], "dracula")
        self.assertEqual(cfg["appearance"]["accent_color"], "#BD93F9")
        self.assertEqual(theme_manager.get_active_theme_id(cfg), "dracula")
        print("  [PASS] Theme application and active id resolution verified.")

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
    suite.addTest(loader.loadTestsFromTestCase(TestThemeManager))

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
