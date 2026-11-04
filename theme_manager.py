"""
theme_manager.py - Open-Volume Theme System
Provides hand-crafted visual palettes for the HUD Overlay and Settings UI.
"""

from typing import Dict, Any, List

THEMES: Dict[str, Dict[str, Any]] = {
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk Mint",
        "emoji": "⚡",
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
    },
    "nord": {
        "id": "nord",
        "name": "Nordic Frost",
        "emoji": "❄️",
        "accent_color": "#88C0D0",
        "bg_color": "#242933",
        "card_bg": "#2E3440",
        "selected_bg": "#3B4252",
        "text_primary": "#ECEFF4",
        "text_secondary": "#D8DEE9",
        "border_color": "#434C5E",
        "track_bg": "#3B4252",
        "danger_color": "#BF616A",
        "badge_text": "#242933"
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula Vampire",
        "emoji": "🦇",
        "accent_color": "#BD93F9",
        "bg_color": "#1E1F29",
        "card_bg": "#282A36",
        "selected_bg": "#44475A",
        "text_primary": "#F8F8F2",
        "text_secondary": "#9E90C0",
        "border_color": "#44475A",
        "track_bg": "#343746",
        "danger_color": "#FF5555",
        "badge_text": "#1E1F29"
    },
    "catppuccin": {
        "id": "catppuccin",
        "name": "Catppuccin Mocha",
        "emoji": "🐱",
        "accent_color": "#CBA6F7",
        "bg_color": "#1E1E2E",
        "card_bg": "#313244",
        "selected_bg": "#45475A",
        "text_primary": "#CDD6F4",
        "text_secondary": "#A6ADC8",
        "border_color": "#585B70",
        "track_bg": "#313244",
        "danger_color": "#F38BA8",
        "badge_text": "#1E1E2E"
    },
    "solarized": {
        "id": "solarized",
        "name": "Solarized Dark",
        "emoji": "🌌",
        "accent_color": "#2AA198",
        "bg_color": "#002B36",
        "card_bg": "#073642",
        "selected_bg": "#0E4D5E",
        "text_primary": "#93A1A1",
        "text_secondary": "#657B83",
        "border_color": "#0B566A",
        "track_bg": "#073642",
        "danger_color": "#DC322F",
        "badge_text": "#002B36"
    },
    "amber": {
        "id": "amber",
        "name": "Retro Amber CRT",
        "emoji": "📟",
        "accent_color": "#FFB000",
        "bg_color": "#0C0C0C",
        "card_bg": "#161616",
        "selected_bg": "#2C200B",
        "text_primary": "#FFE4A0",
        "text_secondary": "#A07820",
        "border_color": "#3D2E0B",
        "track_bg": "#201808",
        "danger_color": "#FF4444",
        "badge_text": "#0C0C0C"
    },
    "oled": {
        "id": "oled",
        "name": "OLED Pure Black",
        "emoji": "🌑",
        "accent_color": "#10B981",
        "bg_color": "#000000",
        "card_bg": "#111111",
        "selected_bg": "#222222",
        "text_primary": "#FFFFFF",
        "text_secondary": "#888888",
        "border_color": "#282828",
        "track_bg": "#1C1C1C",
        "danger_color": "#EF4444",
        "badge_text": "#000000"
    },
    "light": {
        "id": "light",
        "name": "Clean Minimal Light",
        "emoji": "☀️",
        "accent_color": "#0284C7",
        "bg_color": "#F1F5F9",
        "card_bg": "#FFFFFF",
        "selected_bg": "#E2E8F0",
        "text_primary": "#0F172A",
        "text_secondary": "#64748B",
        "border_color": "#CBD5E1",
        "track_bg": "#E2E8F0",
        "danger_color": "#DC2626",
        "badge_text": "#FFFFFF"
    }
}

DEFAULT_THEME_ID = "cyberpunk"

def get_theme(theme_id: str) -> Dict[str, Any]:
    """Retrieves a theme definition by id, falling back to default theme."""
    return THEMES.get(theme_id, THEMES[DEFAULT_THEME_ID])

def list_themes() -> List[Dict[str, Any]]:
    """Returns all available themes as a list."""
    return list(THEMES.values())

def apply_theme_to_config(config: Dict[str, Any], theme_id: str) -> Dict[str, Any]:
    """Merges a theme's color palette into the configuration dictionary."""
    theme = get_theme(theme_id)
    app_cfg = config.setdefault("appearance", {})
    app_cfg["theme"] = theme["id"]
    app_cfg["accent_color"] = theme["accent_color"]
    app_cfg["bg_color"] = theme["bg_color"]
    app_cfg["card_bg"] = theme["card_bg"]
    app_cfg["selected_bg"] = theme["selected_bg"]
    app_cfg["text_primary"] = theme["text_primary"]
    app_cfg["text_secondary"] = theme["text_secondary"]
    app_cfg["border_color"] = theme["border_color"]
    app_cfg["track_bg"] = theme["track_bg"]
    app_cfg["danger_color"] = theme["danger_color"]
    app_cfg["badge_text"] = theme["badge_text"]
    return config

def get_active_theme_id(config: Dict[str, Any]) -> str:
    """Returns the current theme id based on appearance config."""
    app_cfg = config.get("appearance", {})
    t_id = app_cfg.get("theme")
    if t_id and t_id in THEMES:
        return t_id

    # Fallback: check matching accent color
    accent = app_cfg.get("accent_color", "").upper()
    for tid, t in THEMES.items():
        if t["accent_color"].upper() == accent:
            return tid

    return DEFAULT_THEME_ID
