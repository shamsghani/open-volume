import os
import psutil
import comtypes
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

class AudioMixer:
    """Manages system master volume and per-application audio sessions via Windows Core Audio (WASAPI)."""

    def __init__(self):
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        self.apps = []
        self.selected_index = 0
        self.refresh()

    def refresh(self):
        """Scans current audio endpoints and per-app sessions."""
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        new_apps = []

        # 1. Master System Volume (System Wide)
        try:
            speakers = AudioUtilities.GetSpeakers()
            master = speakers.EndpointVolume
            master_vol = int(round(master.GetMasterVolumeLevelScalar() * 100))
            master_muted = bool(master.GetMute())
            new_apps.append({
                'id': 'system_master',
                'name': 'System (Master Volume)',
                'is_master': True,
                'volume': master_vol,
                'muted': master_muted,
                'endpoint': master
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
                    if s.Process:
                        try:
                            pname = s.Process.name()
                        except Exception:
                            pname = f"Process_{s.ProcessId}"
                    else:
                        pname = "System Sounds"

                    clean_name = self._format_name(pname)
                    if clean_name not in grouped:
                        grouped[clean_name] = []
                    grouped[clean_name].append(vol)
                except Exception:
                    continue

            for name in sorted(grouped.keys()):
                vol_objs = grouped[name]
                try:
                    curr_vol = int(round(vol_objs[0].GetMasterVolume() * 100))
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
                    'objs': vol_objs
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
        scalar = target_percent / 100.0

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
