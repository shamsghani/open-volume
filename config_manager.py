import json
import os
import sys

DEFAULT_CONFIG = {
    "mode": "hybrid",
    "hotkey": {
        "ctrl_numlock": True,
        "double_tap_numlock": True,
        "double_tap_max_interval_ms": 400
    },
    "custom_bindings": {
        "toggle_layer": {
            "vk": 0x56, "ctrl": True, "alt": True, "shift": False, "win": False,
            "display": "Ctrl + Alt + V"
        },
        "volume_up": {
            "vk": 0x26, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "Up Arrow"
        },
        "volume_down": {
            "vk": 0x28, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "Down Arrow"
        },
        "next_app": {
            "vk": 0x27, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "Right Arrow"
        },
        "prev_app": {
            "vk": 0x25, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "Left Arrow"
        },
        "toggle_mute": {
            "vk": 0x4D, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "M"
        },
        "exit_layer": {
            "vk": 0x1B, "ctrl": False, "alt": False, "shift": False, "win": False,
            "display": "Escape"
        },
        "toggle_mic_mute": {
            "vk": 0x4D, "ctrl": True, "alt": True, "shift": False, "win": False,
            "display": "Ctrl + Alt + M"
        },
        "play_pause": {
            "vk": 0x20, "ctrl": True, "alt": True, "shift": False, "win": False,
            "display": "Ctrl + Alt + Space"
        },
        "next_track": {
            "vk": 0x27, "ctrl": True, "alt": True, "shift": False, "win": False,
            "display": "Ctrl + Alt + Right"
        },
        "prev_track": {
            "vk": 0x25, "ctrl": True, "alt": True, "shift": False, "win": False,
            "display": "Ctrl + Alt + Left"
        }
    },
    "volume": {
        "step_percent": 5,
        "fine_step_percent": 2,
        "sound_feedback": True,
        "perceptual_curve": True
    },
    "behavior": {
        "auto_hide_seconds": 6,
        "cycle_wraparound": True,
        "start_on_boot": False,
        "follow_focus": True,
        "numpad_media_keys": True
    },
    "pinned_apps": ["Discord", "Spotify", "Google Chrome"],
    "profiles": {
        "gaming": {
            "name": "Gaming Mode",
            "emoji": "🎮",
            "master": 85,
            "apps": { "Discord": 100, "Spotify": 25, "System Sounds": 0 }
        },
        "focus": {
            "name": "Focus / Work",
            "emoji": "🎧",
            "master": 60,
            "apps": { "Spotify": 60, "Google Chrome": 30, "Discord": 0 }
        },
        "cinema": {
            "name": "Cinema / Movie",
            "emoji": "🍿",
            "master": 100,
            "apps": { "VLC Media Player": 100, "Google Chrome": 100, "System Sounds": 0, "Discord": 20 }
        }
    },
    "appearance": {
        "position": "bottom-right",
        "animation_enabled": True,
        "animation_duration_ms": 180,
        "margin_x": 28,
        "margin_y": 60,
        "width": 360,
        "max_visible_apps": 6,
        "theme": "cyberpunk",
        "accent_color": "#00E5A3",
        "bg_color": "#121318",
        "card_bg": "#1A1B24",
        "selected_bg": "#242838",
        "text_primary": "#FFFFFF",
        "text_secondary": "#8E90A6",
        "border_color": "#2A2D3C",
        "track_bg": "#272A38",
        "danger_color": "#FF4B5C",
        "badge_text": "#121318"
    }
}

class ConfigManager:
    def __init__(self, config_path: str = None):
        if config_path is None:
            if getattr(sys, "frozen", False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "config.json")
        self.config_path = config_path
        self.config = self.load()

    def load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                return self._merge_defaults(user_cfg, DEFAULT_CONFIG)
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}. Using defaults.")
        return DEFAULT_CONFIG.copy()

    def _merge_defaults(self, target: dict, defaults: dict) -> dict:
        res = defaults.copy()
        for k, v in target.items():
            if isinstance(v, dict) and k in res and isinstance(res[k], dict):
                res[k] = self._merge_defaults(v, res[k])
            else:
                res[k] = v
        return res

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving {self.config_path}: {e}")

    def get(self, *keys, default=None):
        curr = self.config
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return default
        return curr

