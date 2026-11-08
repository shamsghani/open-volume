"""
audio_mixer.py - Windows Core Audio (WASAPI) Session & Device Manager
Provides master and per-application volume control, live peak metering,
microphone toggle, active window auto-focus, app pinning, and audio profiles.
"""

import os
import psutil
import ctypes
from ctypes import wintypes
import comtypes
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume, IAudioMeterInformation

user32 = ctypes.windll.user32

class AudioMixer:
    """Manages system master volume, per-app audio sessions, and microphone via WASAPI."""

    def __init__(self, perceptual_curve: bool = False, pinned_apps: list = None):
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        self.perceptual_curve = perceptual_curve
        self.pinned_apps = [p.lower() for p in (pinned_apps or [])]
        self.follow_focus = True
        self.apps = []
        self.selected_index = 0
        self.current_device_name = "Default Speakers"
        self.refresh()

    def set_perceptual_curve(self, enabled: bool):
        """Enables or disables logarithmic / perceptual dB volume mapping."""
        self.perceptual_curve = enabled

    def set_pinned_apps(self, pinned_apps: list):
        """Sets the list of application names that take priority indices."""
        self.pinned_apps = [p.lower() for p in (pinned_apps or [])]
        self.refresh()

    def percent_to_scalar(self, percent: int) -> float:
        """Converts an integer percentage (0-100) to CoreAudio scalar (0.0-1.0)."""
        p = max(0.0, min(1.0, percent / 100.0))
        if not self.perceptual_curve:
            return p
        # Perceptual power transfer curve (exponent ~1.8)
        return p ** 1.8

    def scalar_to_percent(self, scalar: float) -> int:
        """Converts CoreAudio scalar (0.0-1.0) back to integer percentage (0-100)."""
        s = max(0.0, min(1.0, float(scalar)))
        if not self.perceptual_curve:
            return int(round(s * 100))
        if s <= 0.0:
            return 0
        return max(0, min(100, int(round((s ** (1.0 / 1.8)) * 100))))

    def refresh(self):
        """Scans current audio endpoints, per-app sessions, and active audio device."""
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        new_apps = []

        # 1. Master System Volume & Device Name
        try:
            speakers = AudioUtilities.GetSpeakers()
            self.current_device_name = getattr(speakers, "FriendlyName", "Default Speakers")
            master = speakers.EndpointVolume
            raw_scalar = master.GetMasterVolumeLevelScalar()
            master_vol = self.scalar_to_percent(raw_scalar)
            master_muted = bool(master.GetMute())

            # Query peak meter for master
            master_meter = None
            try:
                master_meter = master.QueryInterface(IAudioMeterInformation)
            except Exception:
                pass

            new_apps.append({
                'id': 'system_master',
                'name': 'System (Master Volume)',
                'is_master': True,
                'volume': master_vol,
                'muted': master_muted,
                'endpoint': master,
                'meter': master_meter,
                'meters': [master_meter] if master_meter else [],
                'raw_name': 'master'
            })
        except Exception as e:
            print(f"[AudioMixer] Error querying master volume: {e}")

        # 2. Per-App Audio Sessions
        try:
            sessions = AudioUtilities.GetAllSessions()
            grouped = {}
            for s in sessions:
                try:
                    vol = s._ctl.QueryInterface(ISimpleAudioVolume)
                    meter = None
                    try:
                        meter = s._ctl.QueryInterface(IAudioMeterInformation)
                    except Exception:
                        pass

                    if s.Process:
                        try:
                            pname = s.Process.name()
                        except Exception:
                            pname = f"Process_{s.ProcessId}"
                    else:
                        pname = "System Sounds"

                    clean_name = self._format_name(pname)
                    if clean_name not in grouped:
                        grouped[clean_name] = {'vols': [], 'meters': [], 'raw_name': pname}
                    grouped[clean_name]['vols'].append(vol)
                    if meter:
                        grouped[clean_name]['meters'].append(meter)
                except Exception:
                    continue

            # Sort apps: pinned apps first, then alphabetical
            def sort_key(name):
                n_lower = name.lower()
                for p_idx, pin in enumerate(self.pinned_apps):
                    if pin in n_lower or n_lower in pin:
                        return (0, p_idx, name.lower())
                return (1, 0, name.lower())

            sorted_names = sorted(grouped.keys(), key=sort_key)

            for name in sorted_names:
                entry = grouped[name]
                vol_objs = entry['vols']
                meter_objs = entry['meters']
                raw_pname = entry['raw_name']
                try:
                    raw_scalar = vol_objs[0].GetMasterVolume()
                    curr_vol = self.scalar_to_percent(raw_scalar)
                    curr_mute = bool(vol_objs[0].GetMute())
                except Exception:
                    curr_vol = 100
                    curr_mute = False

                new_apps.append({
                    'id': f"app_{name.lower().replace(' ', '_')}",
                    'name': name,
                    'is_master': False,
                    'volume': curr_vol,
                    'muted': curr_mute,
                    'objs': vol_objs,
                    'meter': meter_objs[0] if meter_objs else None,
                    'meters': meter_objs,
                    'raw_name': raw_pname
                })
        except Exception as e:
            print(f"[AudioMixer] Error querying audio sessions: {e}")

        self.apps = new_apps
        if self.selected_index >= len(self.apps):
            self.selected_index = max(0, len(self.apps) - 1)

    def _format_name(self, raw_name: str) -> str:
        name = raw_name
        if name.lower().endswith('.exe'):
            name = name[:-4]
        lower = name.lower()
        mapping = {
            'chrome': 'Google Chrome',
            'msedge': 'Microsoft Edge',
            'msedgewebview2': 'Edge WebView',
            'spotify': 'Spotify',
            'discord': 'Discord',
            'antigravity ide': 'Antigravity IDE',
            'obs64': 'OBS Studio',
            'steam': 'Steam',
            'vlc': 'VLC Media Player',
            'firefox': 'Firefox',
            'opera': 'Opera Browser',
            'brave': 'Brave Browser',
            'devenv': 'Visual Studio',
            'code': 'VS Code',
            'windowsterminal': 'Windows Terminal'
        }
        return mapping.get(lower, name)

    def get_apps(self):
        return self.apps

    # Alias for get_apps
    def get_sessions(self):
        return self.apps

    def get_selected_index(self):
        return self.selected_index

    def get_selected_app(self):
        if 0 <= self.selected_index < len(self.apps):
            return self.apps[self.selected_index]
        return None

    def select_next(self):
        if not self.apps:
            return None
        self.selected_index = (self.selected_index + 1) % len(self.apps)
        return self.get_selected_app()

    def select_prev(self):
        if not self.apps:
            return None
        self.selected_index = (self.selected_index - 1) % len(self.apps)
        return self.get_selected_app()

    def select_index(self, index: int):
        if 0 <= index < len(self.apps):
            self.selected_index = index
        return self.get_selected_app()

    def adjust_volume(self, delta: int):
        """Adjusts the selected app's volume by delta (-100 to 100)."""
        app = self.get_selected_app()
        if not app:
            return 0
        new_vol = max(0, min(100, app['volume'] + delta))
        return self.set_volume(new_vol)

    def set_volume(self, target_percent: int):
        """Sets the selected app's volume (0 to 100)."""
        app = self.get_selected_app()
        if not app:
            return 0
        target_percent = max(0, min(100, target_percent))
        scalar = self.percent_to_scalar(target_percent)

        if app['is_master']:
            try:
                app['endpoint'].SetMasterVolumeLevelScalar(scalar, None)
                app['volume'] = target_percent
            except Exception as e:
                print(f"[AudioMixer] Error setting master volume: {e}")
        else:
            for vol_obj in app.get('objs', []):
                try:
                    vol_obj.SetMasterVolume(scalar, None)
                except Exception as e:
                    print(f"[AudioMixer] Error setting session volume: {e}")
            app['volume'] = target_percent

        return app['volume']

    def toggle_mute(self):
        """Toggles mute on the selected app."""
        app = self.get_selected_app()
        if not app:
            return False
        new_mute = not app['muted']

        if app['is_master']:
            try:
                app['endpoint'].SetMute(new_mute, None)
                app['muted'] = new_mute
            except Exception as e:
                print(f"[AudioMixer] Error toggling master mute: {e}")
        else:
            for vol_obj in app.get('objs', []):
                try:
                    vol_obj.SetMute(new_mute, None)
                except Exception as e:
                    print(f"[AudioMixer] Error toggling session mute: {e}")
            app['muted'] = new_mute

        return app['muted']

    # --- Live Peak Metering ---
    def get_peak_levels(self) -> list:
        """Returns a list of float peak audio levels (0.0 to 1.0) for each app in self.apps."""
        peaks = []
        for app in self.apps:
            meters = app.get('meters') or ([app.get('meter')] if app.get('meter') else [])
            max_p = 0.0
            for meter in meters:
                if meter:
                    try:
                        p = meter.GetPeakValue()
                        if p > max_p:
                            max_p = float(p)
                    except Exception:
                        pass
            peaks.append(min(1.0, max(0.0, max_p)))
        return peaks

    def get_selected_peak_level(self) -> float:
        """Returns the float peak level (0.0 to 1.0) for the currently selected app."""
        if 0 <= self.selected_index < len(self.apps):
            app = self.apps[self.selected_index]
            meters = app.get('meters') or ([app.get('meter')] if app.get('meter') else [])
            max_p = 0.0
            for meter in meters:
                if meter:
                    try:
                        p = meter.GetPeakValue()
                        if p > max_p:
                            max_p = float(p)
                    except Exception:
                        pass
            return min(1.0, max(0.0, max_p))
        return 0.0

    # --- Active Window Auto-Select ("Follow Focus") ---
    def get_foreground_process_name(self) -> str:
        """Retrieves the executable name of the current foreground window."""
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return ""
            return psutil.Process(pid.value).name()
        except Exception:
            return ""

    def auto_select_foreground_app(self) -> bool:
        """Automatically pre-selects the foreground application in the mixer."""
        pname = self.get_foreground_process_name()
        if not pname:
            return False

        clean_pname = self._format_name(pname).lower()
        # Search among non-master apps
        for idx in range(1, len(self.apps)):
            app_name = self.apps[idx]['name'].lower()
            raw_name = self.apps[idx].get('raw_name', '').lower()
            if clean_pname in app_name or app_name in clean_pname or clean_pname in raw_name:
                self.selected_index = idx
                return True
        return False

    # --- Microphone Management ---
    def get_microphone_info(self) -> dict:
        """Returns default microphone status (name, volume, muted)."""
        try:
            mic = AudioUtilities.GetMicrophone()
            if not mic:
                return {'name': 'No Microphone', 'volume': 0, 'muted': True, 'present': False}
            fname = getattr(mic, 'FriendlyName', 'Default Microphone')
            unk = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep = unk.QueryInterface(IAudioEndpointVolume)
            raw_scalar = ep.GetMasterVolumeLevelScalar()
            vol = self.scalar_to_percent(raw_scalar)
            muted = bool(ep.GetMute())
            return {'name': fname, 'volume': vol, 'muted': muted, 'present': True}
        except Exception as e:
            return {'name': 'Microphone', 'volume': 100, 'muted': False, 'present': False, 'error': str(e)}

    def toggle_microphone_mute(self) -> bool:
        """Toggles mute on the system default recording microphone."""
        try:
            mic = AudioUtilities.GetMicrophone()
            if not mic:
                return False
            unk = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep = unk.QueryInterface(IAudioEndpointVolume)
            new_mute = not ep.GetMute()
            ep.SetMute(new_mute, None)
            print(f"[AudioMixer] Microphone mute toggled -> {new_mute}")
            return new_mute
        except Exception as e:
            print(f"[AudioMixer] Error toggling mic mute: {e}")
            return False

    def set_microphone_volume(self, target_percent: int) -> int:
        """Sets the system default recording microphone volume."""
        try:
            mic = AudioUtilities.GetMicrophone()
            if not mic:
                return 0
            unk = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep = unk.QueryInterface(IAudioEndpointVolume)
            target_percent = max(0, min(100, target_percent))
            scalar = self.percent_to_scalar(target_percent)
            ep.SetMasterVolumeLevelScalar(scalar, None)
            return target_percent
        except Exception as e:
            print(f"[AudioMixer] Error setting mic volume: {e}")
            return 0

    # --- Audio Profiles / Presets ---
    def apply_profile(self, profile: dict) -> bool:
        """Applies a volume profile to master and matching applications."""
        try:
            master_vol = profile.get("master")
            if master_vol is not None and self.apps:
                orig_idx = self.selected_index
                self.selected_index = 0
                self.set_volume(master_vol)
                self.selected_index = orig_idx

            app_targets = profile.get("apps", {})
            for app in self.apps[1:]:
                aname = app["name"].lower()
                for target_name, target_vol in app_targets.items():
                    tlower = target_name.lower()
                    if tlower in aname or aname in tlower:
                        if target_vol == 0:
                            app['muted'] = True
                            for obj in app.get('objs', []):
                                try:
                                    obj.SetMute(True, None)
                                except Exception:
                                    pass
                        else:
                            scalar = self.percent_to_scalar(target_vol)
                            for obj in app.get('objs', []):
                                try:
                                    obj.SetMasterVolume(scalar, None)
                                    obj.SetMute(False, None)
                                except Exception:
                                    pass
                            app['volume'] = target_vol
                            app['muted'] = False
            return True
        except Exception as e:
            print(f"[AudioMixer] Error applying profile: {e}")
            return False

    def get_current_playback_device_name(self) -> str:
        """Returns the name of the currently active default audio output device."""
        return self.current_device_name
