use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotkeyConfig {
    #[serde(default = "default_true")]
    pub ctrl_numlock: bool,
    #[serde(default = "default_true")]
    pub double_tap_numlock: bool,
    #[serde(default = "default_400")]
    pub double_tap_max_interval_ms: u64,
}

impl Default for HotkeyConfig {
    fn default() -> Self {
        Self {
            ctrl_numlock: true,
            double_tap_numlock: true,
            double_tap_max_interval_ms: 400,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BindingConfig {
    pub vk: u32,
    #[serde(default)]
    pub ctrl: bool,
    #[serde(default)]
    pub alt: bool,
    #[serde(default)]
    pub shift: bool,
    #[serde(default)]
    pub win: bool,
    #[serde(default)]
    pub display: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeConfig {
    #[serde(default = "default_5")]
    pub step_percent: i32,
    #[serde(default = "default_2")]
    pub fine_step_percent: i32,
    #[serde(default = "default_true")]
    pub sound_feedback: bool,
    #[serde(default = "default_true")]
    pub perceptual_curve: bool,
}

impl Default for VolumeConfig {
    fn default() -> Self {
        Self {
            step_percent: 5,
            fine_step_percent: 2,
            sound_feedback: true,
            perceptual_curve: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehaviorConfig {
    #[serde(default = "default_6")]
    pub auto_hide_seconds: u64,
    #[serde(default = "default_true")]
    pub cycle_wraparound: bool,
    #[serde(default)]
    pub start_on_boot: bool,
    #[serde(default = "default_true")]
    pub follow_focus: bool,
    #[serde(default = "default_true")]
    pub numpad_media_keys: bool,
}

impl Default for BehaviorConfig {
    fn default() -> Self {
        Self {
            auto_hide_seconds: 6,
            cycle_wraparound: true,
            start_on_boot: false,
            follow_focus: true,
            numpad_media_keys: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProfileConfig {
    pub name: String,
    pub emoji: String,
    pub master: i32,
    #[serde(default)]
    pub apps: HashMap<String, i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppearanceConfig {
    #[serde(default = "default_position")]
    pub position: String,
    #[serde(default = "default_true")]
    pub animation_enabled: bool,
    #[serde(default = "default_180")]
    pub animation_duration_ms: u64,
    #[serde(default = "default_28")]
    pub margin_x: i32,
    #[serde(default = "default_60")]
    pub margin_y: i32,
    #[serde(default = "default_360")]
    pub width: i32,
    #[serde(default = "default_6_i32")]
    pub max_visible_apps: usize,
    #[serde(default = "default_theme_id")]
    pub theme: String,
    #[serde(default = "default_accent_color")]
    pub accent_color: String,
    #[serde(default = "default_bg_color")]
    pub bg_color: String,
    #[serde(default = "default_card_bg")]
    pub card_bg: String,
    #[serde(default = "default_selected_bg")]
    pub selected_bg: String,
    #[serde(default = "default_text_primary")]
    pub text_primary: String,
    #[serde(default = "default_text_secondary")]
    pub text_secondary: String,
    #[serde(default = "default_border_color")]
    pub border_color: String,
    #[serde(default = "default_track_bg")]
    pub track_bg: String,
    #[serde(default = "default_danger_color")]
    pub danger_color: String,
    #[serde(default = "default_badge_text")]
    pub badge_text: String,
}

impl Default for AppearanceConfig {
    fn default() -> Self {
        Self {
            position: "top-center".to_string(),
            animation_enabled: true,
            animation_duration_ms: 180,
            margin_x: 28,
            margin_y: 60,
            width: 360,
            max_visible_apps: 6,
            theme: "cyberpunk".to_string(),
            accent_color: "#00E5A3".to_string(),
            bg_color: "#121318".to_string(),
            card_bg: "#1A1B24".to_string(),
            selected_bg: "#242838".to_string(),
            text_primary: "#FFFFFF".to_string(),
            text_secondary: "#8E90A6".to_string(),
            border_color: "#2A2D3C".to_string(),
            track_bg: "#272A38".to_string(),
            danger_color: "#FF4B5C".to_string(),
            badge_text: "#121318".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_mode")]
    pub mode: String,
    #[serde(default)]
    pub hotkey: HotkeyConfig,
    #[serde(default)]
    pub custom_bindings: HashMap<String, BindingConfig>,
    #[serde(default)]
    pub volume: VolumeConfig,
    #[serde(default)]
    pub behavior: BehaviorConfig,
    #[serde(default = "default_pinned_apps")]
    pub pinned_apps: Vec<String>,
    #[serde(default)]
    pub profiles: HashMap<String, ProfileConfig>,
    #[serde(default)]
    pub appearance: AppearanceConfig,
}

impl Default for Config {
    fn default() -> Self {
        let mut custom_bindings = HashMap::new();
        custom_bindings.insert(
            "toggle_layer".to_string(),
            BindingConfig {
                vk: 0x56, // 'V'
                ctrl: true,
                alt: true,
                shift: false,
                win: false,
                display: "Ctrl + Alt + V".to_string(),
            },
        );
        custom_bindings.insert(
            "volume_up".to_string(),
            BindingConfig {
                vk: 0x26, // Up Arrow
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "Up Arrow".to_string(),
            },
        );
        custom_bindings.insert(
            "volume_down".to_string(),
            BindingConfig {
                vk: 0x28, // Down Arrow
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "Down Arrow".to_string(),
            },
        );
        custom_bindings.insert(
            "next_app".to_string(),
            BindingConfig {
                vk: 0x27, // Right Arrow
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "Right Arrow".to_string(),
            },
        );
        custom_bindings.insert(
            "prev_app".to_string(),
            BindingConfig {
                vk: 0x25, // Left Arrow
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "Left Arrow".to_string(),
            },
        );
        custom_bindings.insert(
            "toggle_mute".to_string(),
            BindingConfig {
                vk: 0x4D, // 'M'
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "M".to_string(),
            },
        );
        custom_bindings.insert(
            "exit_layer".to_string(),
            BindingConfig {
                vk: 0x1B, // Escape
                ctrl: false,
                alt: false,
                shift: false,
                win: false,
                display: "Escape".to_string(),
            },
        );
        custom_bindings.insert(
            "toggle_mic_mute".to_string(),
            BindingConfig {
                vk: 0x4D, // 'M'
                ctrl: true,
                alt: true,
                shift: false,
                win: false,
                display: "Ctrl + Alt + M".to_string(),
            },
        );
        custom_bindings.insert(
            "play_pause".to_string(),
            BindingConfig {
                vk: 0x20, // Space
                ctrl: true,
                alt: true,
                shift: false,
                win: false,
                display: "Ctrl + Alt + Space".to_string(),
            },
        );
        custom_bindings.insert(
            "next_track".to_string(),
            BindingConfig {
                vk: 0x27, // Right Arrow
                ctrl: true,
                alt: true,
                shift: false,
                win: false,
                display: "Ctrl + Alt + Right".to_string(),
            },
        );
        custom_bindings.insert(
            "prev_track".to_string(),
            BindingConfig {
                vk: 0x25, // Left Arrow
                ctrl: true,
                alt: true,
                shift: false,
                win: false,
                display: "Ctrl + Alt + Left".to_string(),
            },
        );

        let mut profiles = HashMap::new();
        let mut gaming_apps = HashMap::new();
        gaming_apps.insert("Discord".to_string(), 100);
        gaming_apps.insert("Spotify".to_string(), 25);
        gaming_apps.insert("System Sounds".to_string(), 0);
        profiles.insert(
            "gaming".to_string(),
            ProfileConfig {
                name: "Gaming Mode".to_string(),
                emoji: "🎮".to_string(),
                master: 85,
                apps: gaming_apps,
            },
        );

        let mut focus_apps = HashMap::new();
        focus_apps.insert("Spotify".to_string(), 60);
        focus_apps.insert("Google Chrome".to_string(), 30);
        focus_apps.insert("Discord".to_string(), 0);
        profiles.insert(
            "focus".to_string(),
            ProfileConfig {
                name: "Focus / Work".to_string(),
                emoji: "🎧".to_string(),
                master: 60,
                apps: focus_apps,
            },
        );

        let mut cinema_apps = HashMap::new();
        cinema_apps.insert("VLC Media Player".to_string(), 100);
        cinema_apps.insert("Google Chrome".to_string(), 100);
        cinema_apps.insert("System Sounds".to_string(), 0);
        cinema_apps.insert("Discord".to_string(), 20);
        profiles.insert(
            "cinema".to_string(),
            ProfileConfig {
                name: "Cinema / Movie".to_string(),
                emoji: "🍿".to_string(),
                master: 100,
                apps: cinema_apps,
            },
        );

        Self {
            mode: "hybrid".to_string(),
            hotkey: HotkeyConfig::default(),
            custom_bindings,
            volume: VolumeConfig::default(),
            behavior: BehaviorConfig::default(),
            pinned_apps: default_pinned_apps(),
            profiles,
            appearance: AppearanceConfig::default(),
        }
    }
}

// Default helpers
fn default_true() -> bool { true }
fn default_mode() -> String { "hybrid".to_string() }
fn default_400() -> u64 { 400 }
fn default_5() -> i32 { 5 }
fn default_2() -> i32 { 2 }
fn default_6() -> u64 { 6 }
fn default_180() -> u64 { 180 }
fn default_28() -> i32 { 28 }
fn default_60() -> i32 { 60 }
fn default_360() -> i32 { 360 }
fn default_6_i32() -> usize { 6 }
fn default_position() -> String { "top-center".to_string() }
fn default_theme_id() -> String { "cyberpunk".to_string() }
fn default_accent_color() -> String { "#00E5A3".to_string() }
fn default_bg_color() -> String { "#121318".to_string() }
fn default_card_bg() -> String { "#1A1B24".to_string() }
fn default_selected_bg() -> String { "#242838".to_string() }
fn default_text_primary() -> String { "#FFFFFF".to_string() }
fn default_text_secondary() -> String { "#8E90A6".to_string() }
fn default_border_color() -> String { "#2A2D3C".to_string() }
fn default_track_bg() -> String { "#272A38".to_string() }
fn default_danger_color() -> String { "#FF4B5C".to_string() }
fn default_badge_text() -> String { "#121318".to_string() }
fn default_pinned_apps() -> Vec<String> {
    vec!["Discord".to_string(), "Spotify".to_string(), "Google Chrome".to_string()]
}

// -------------------------------------------------------------
// Theme Definitions
// -------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Theme {
    pub id: String,
    pub name: String,
    pub emoji: String,
    pub accent_color: String,
    pub bg_color: String,
    pub card_bg: String,
    pub selected_bg: String,
    pub text_primary: String,
    pub text_secondary: String,
    pub border_color: String,
    pub track_bg: String,
    pub danger_color: String,
    pub badge_text: String,
}

pub fn list_themes() -> Vec<Theme> {
    vec![
        Theme {
            id: "cyberpunk".into(),
            name: "Cyberpunk Mint".into(),
            emoji: "⚡".into(),
            accent_color: "#00E5A3".into(),
            bg_color: "#121318".into(),
            card_bg: "#1A1B24".into(),
            selected_bg: "#242838".into(),
            text_primary: "#FFFFFF".into(),
            text_secondary: "#8E90A6".into(),
            border_color: "#2A2D3C".into(),
            track_bg: "#272A38".into(),
            danger_color: "#FF4B5C".into(),
            badge_text: "#121318".into(),
        },
        Theme {
            id: "nord".into(),
            name: "Nordic Frost".into(),
            emoji: "❄️".into(),
            accent_color: "#88C0D0".into(),
            bg_color: "#242933".into(),
            card_bg: "#2E3440".into(),
            selected_bg: "#3B4252".into(),
            text_primary: "#ECEFF4".into(),
            text_secondary: "#D8DEE9".into(),
            border_color: "#434C5E".into(),
            track_bg: "#3B4252".into(),
            danger_color: "#BF616A".into(),
            badge_text: "#242933".into(),
        },
        Theme {
            id: "dracula".into(),
            name: "Dracula Vampire".into(),
            emoji: "🦇".into(),
            accent_color: "#BD93F9".into(),
            bg_color: "#1E1F29".into(),
            card_bg: "#282A36".into(),
            selected_bg: "#44475A".into(),
            text_primary: "#F8F8F2".into(),
            text_secondary: "#9E90C0".into(),
            border_color: "#44475A".into(),
            track_bg: "#343746".into(),
            danger_color: "#FF5555".into(),
            badge_text: "#1E1F29".into(),
        },
        Theme {
            id: "catppuccin".into(),
            name: "Catppuccin Mocha".into(),
            emoji: "🐱".into(),
            accent_color: "#CBA6F7".into(),
            bg_color: "#1E1E2E".into(),
            card_bg: "#313244".into(),
            selected_bg: "#45475A".into(),
            text_primary: "#CDD6F4".into(),
            text_secondary: "#A6ADC8".into(),
            border_color: "#585B70".into(),
            track_bg: "#313244".into(),
            danger_color: "#F38BA8".into(),
            badge_text: "#1E1E2E".into(),
        },
        Theme {
            id: "solarized".into(),
            name: "Solarized Dark".into(),
            emoji: "🌌".into(),
            accent_color: "#2AA198".into(),
            bg_color: "#002B36".into(),
            card_bg: "#073642".into(),
            selected_bg: "#0E4D5E".into(),
            text_primary: "#93A1A1".into(),
            text_secondary: "#657B83".into(),
            border_color: "#0B566A".into(),
            track_bg: "#073642".into(),
            danger_color: "#DC322F".into(),
            badge_text: "#002B36".into(),
        },
        Theme {
            id: "amber".into(),
            name: "Retro Amber CRT".into(),
            emoji: "📟".into(),
            accent_color: "#FFB000".into(),
            bg_color: "#0C0C0C".into(),
            card_bg: "#161616".into(),
            selected_bg: "#2C200B".into(),
            text_primary: "#FFE4A0".into(),
            text_secondary: "#A07820".into(),
            border_color: "#3D2E0B".into(),
            track_bg: "#201808".into(),
            danger_color: "#FF4444".into(),
            badge_text: "#0C0C0C".into(),
        },
        Theme {
            id: "oled".into(),
            name: "OLED Pure Black".into(),
            emoji: "🌑".into(),
            accent_color: "#10B981".into(),
            bg_color: "#000000".into(),
            card_bg: "#111111".into(),
            selected_bg: "#222222".into(),
            text_primary: "#FFFFFF".into(),
            text_secondary: "#888888".into(),
            border_color: "#282828".into(),
            track_bg: "#1C1C1C".into(),
            danger_color: "#EF4444".into(),
            badge_text: "#000000".into(),
        },
        Theme {
            id: "light".into(),
            name: "Clean Minimal Light".into(),
            emoji: "☀️".into(),
            accent_color: "#0284C7".into(),
            bg_color: "#F1F5F9".into(),
            card_bg: "#FFFFFF".into(),
            selected_bg: "#E2E8F0".into(),
            text_primary: "#0F172A".into(),
            text_secondary: "#64748B".into(),
            border_color: "#CBD5E1".into(),
            track_bg: "#E2E8F0".into(),
            danger_color: "#DC2626".into(),
            badge_text: "#FFFFFF".into(),
        },
    ]
}

pub fn get_theme(theme_id: &str) -> Theme {
    let themes = list_themes();
    themes.into_iter().find(|t| t.id == theme_id).unwrap_or_else(|| {
        list_themes().into_iter().next().unwrap()
    })
}

impl Config {
    pub fn config_path() -> PathBuf {
        if let Ok(exe) = std::env::current_exe() {
            if let Some(dir) = exe.parent() {
                let candidate = dir.join("config.json");
                if candidate.exists() {
                    return candidate;
                }
            }
        }
        PathBuf::from("config.json")
    }

    pub fn load() -> Self {
        let path = Self::config_path();
        if path.exists() {
            if let Ok(contents) = fs::read_to_string(&path) {
                if let Ok(cfg) = serde_json::from_str::<Config>(&contents) {
                    return cfg;
                }
            }
        }
        Self::default()
    }

    pub fn save(&self) -> bool {
        let path = Self::config_path();
        if let Ok(json) = serde_json::to_string_pretty(self) {
            return fs::write(path, json).is_ok();
        }
        false
    }

    pub fn apply_theme(&mut self, theme_id: &str) {
        let t = get_theme(theme_id);
        self.appearance.theme = t.id;
        self.appearance.accent_color = t.accent_color;
        self.appearance.bg_color = t.bg_color;
        self.appearance.card_bg = t.card_bg;
        self.appearance.selected_bg = t.selected_bg;
        self.appearance.text_primary = t.text_primary;
        self.appearance.text_secondary = t.text_secondary;
        self.appearance.border_color = t.border_color;
        self.appearance.track_bg = t.track_bg;
        self.appearance.danger_color = t.danger_color;
        self.appearance.badge_text = t.badge_text;
    }
}

// -------------------------------------------------------------
// Perceptual Audio Math Helpers
// -------------------------------------------------------------

/// Converts a 0..100 percentage to a WASAPI scalar [0.0, 1.0] using a perceptual curve.
pub fn percent_to_scalar(percent: i32, perceptual: bool) -> f32 {
    let p = percent.clamp(0, 100) as f32;
    if !perceptual {
        return p / 100.0;
    }
    if p <= 0.0 {
        return 0.0;
    }
    // Perceptual logarithmic dB curve: (10^(3*p/100) - 1) / (10^3 - 1) or cubic approximation
    // Exact mapping matching the verified Python formula:
    // scalar = 0.001 * (10.0 ** (3.0 * p / 100.0)) - 0.001
    // normalized to exactly reach 1.0 at p=100
    let factor = (10.0f32.powf(3.0 * (p / 100.0)) - 1.0) / (1000.0 - 1.0);
    factor.clamp(0.0, 1.0)
}

/// Converts a WASAPI scalar [0.0, 1.0] to a 0..100 percentage.
pub fn scalar_to_percent(scalar: f32, perceptual: bool) -> i32 {
    let s = scalar.clamp(0.0, 1.0);
    if !perceptual {
        return (s * 100.0).round() as i32;
    }
    if s <= 0.0001 {
        return 0;
    }
    // Inverse: p = (log10(s * 999.0 + 1.0) / 3.0) * 100.0
    let inner = s * 999.0 + 1.0;
    let p = (inner.log10() / 3.0) * 100.0;
    p.round().clamp(0.0, 100.0) as i32
}

/// Parse hex color "#RRGGBB" to Win32 COLORREF (0x00BBGGRR)
pub fn hex_to_colorref(hex: &str) -> u32 {
    let clean = hex.trim().trim_start_matches('#');
    if clean.len() >= 6 {
        if let Ok(num) = u32::from_str_radix(&clean[..6], 16) {
            let r = (num >> 16) & 0xFF;
            let g = (num >> 8) & 0xFF;
            let b = num & 0xFF;
            return r | (g << 8) | (b << 16); // Win32 RGB macro: R | (G << 8) | (B << 16)
        }
    }
    0x00FFFFFF // fallback white
}
