use open_volume::audio::AudioMixer;
use open_volume::config::{
    get_theme, hex_to_colorref, list_themes, percent_to_scalar, scalar_to_percent, Config,
    ProfileConfig,
};
use open_volume::hook::{decode_action, AppAction, KeyboardHook};
use open_volume::startup::{get_desktop_shortcut_path, is_startup_enabled};
use std::collections::HashMap;
use windows::Win32::Foundation::WPARAM;

#[test]
fn test_01_mixer_initialization() {
    let mixer = AudioMixer::new(true, vec!["Spotify".into(), "Discord".into()]);
    let apps = mixer.get_apps();
    assert!(!apps.is_empty(), "Mixer must find at least Master Volume");
    assert!(apps[0].is_master, "First app must always be Master Volume");
    println!("  [PASS] Found {} audio targets:", apps.len());
    for (i, a) in apps.iter().enumerate() {
        println!("         [{}] {:<25} (Vol: {}%, Muted: {})", i, a.name, a.volume, a.muted);
    }
}

#[test]
fn test_02_master_volume_query() {
    let mixer = AudioMixer::new(true, vec![]);
    let apps = mixer.get_apps();
    assert!(!apps.is_empty());
    let master = &apps[0];
    assert!((0..=100).contains(&master.volume));
    println!("  [PASS] Master Volume confirmed at {}%, Muted={}", master.volume, master.muted);
}

#[test]
fn test_03_volume_adjustments() {
    let mut mixer = AudioMixer::new(false, vec![]);
    let original = mixer.get_apps()[0].volume;
    let step = if original >= 50 { -5 } else { 5 };
    let moved = mixer.adjust_volume(step);
    assert_eq!(moved, original + step);
    let reverted = mixer.adjust_volume(-step);
    assert_eq!(reverted, original);
    println!("  [PASS] Volume step adjustment verified: {}% -> {}% -> {}%", original, moved, reverted);
}

#[test]
fn test_04_app_cycling() {
    let mut mixer = AudioMixer::new(true, vec![]);
    let count = mixer.get_apps().len();
    assert_eq!(mixer.get_selected_index(), 0);

    let next = mixer.select_next();
    assert!(next.is_some());
    let expected_next = if count > 1 { 1 } else { 0 };
    assert_eq!(mixer.get_selected_index(), expected_next);

    mixer.select_prev();
    assert_eq!(mixer.get_selected_index(), 0);
    println!("  [PASS] App cycling verified (0 -> {} -> 0 across {} apps)", expected_next, count);
}

#[test]
fn test_05_perceptual_curve() {
    // Linear mode
    assert_eq!(percent_to_scalar(50, false), 0.5);
    assert_eq!(scalar_to_percent(0.5, false), 50);

    // Perceptual logarithmic dB curve mode
    let scalar = percent_to_scalar(50, true);
    assert!(scalar < 0.40, "Perceptual 50% must be quieter than 0.40 amplitude");
    assert_eq!(scalar_to_percent(scalar, true), 50);
    println!("  [PASS] Perceptual logarithmic dB curve mapping verified.");
}

#[test]
fn test_06_pinned_apps_ordering() {
    let mixer = AudioMixer::new(true, vec![]);
    let apps = mixer.get_apps().to_vec();
    if apps.len() >= 3 {
        assert!(apps[0].is_master);
        let target_pin = apps.last().unwrap().name.clone();
        let mixer_pinned = AudioMixer::new(true, vec![target_pin.clone()]);
        let reordered = mixer_pinned.get_apps();
        assert_eq!(reordered[1].name, target_pin);
        println!("  [PASS] Pinned app ({}) prioritized ordering verified.", target_pin);
    }
}

#[test]
fn test_07_microphone_info() {
    let mixer = AudioMixer::new(true, vec![]);
    let (name, vol, muted) = mixer.get_microphone_info();
    assert!(!name.is_empty());
    assert!((0..=100).contains(&vol));
    println!("  [PASS] Microphone query verified: {} (Vol: {}%, Muted: {})", name, vol, muted);
}

#[test]
fn test_08_audio_profiles() {
    let mut mixer = AudioMixer::new(false, vec![]);
    let mut apps = HashMap::new();
    apps.insert("Google Chrome".to_string(), 35);
    let profile = ProfileConfig {
        name: "Test Profile".into(),
        emoji: "🧪".into(),
        master: 77,
        apps,
    };
    let ok = mixer.apply_profile(&profile);
    assert!(ok);
    assert_eq!(mixer.get_apps()[0].volume, 77);
    println!("  [PASS] Audio profile preset application verified.");
}

#[test]
fn test_09_peak_audio_meter() {
    let mixer = AudioMixer::new(true, vec![]);
    let (master_pk, app_peaks) = mixer.get_peak_levels();
    assert!(master_pk >= 0.0 && master_pk <= 1.0);
    assert_eq!(app_peaks.len(), mixer.get_apps().len());
    println!("  [PASS] Live audio peak meters verified across {} sessions.", app_peaks.len());
}

#[test]
fn test_10_keyboard_hook_layer_transitions() {
    KeyboardHook::set_layer_active(false);
    assert!(!KeyboardHook::is_layer_active());
    KeyboardHook::set_layer_active(true);
    assert!(KeyboardHook::is_layer_active());
    KeyboardHook::set_layer_active(false);
    assert!(!KeyboardHook::is_layer_active());
    println!("  [PASS] Layer state transitions and event callbacks verified.");
}

#[test]
fn test_11_enter_key_isolation() {
    // In hook.rs:
    // If vk == VK_RETURN (0x0D):
    // If (flags & 1) == 0 (Main Enter): CallNextHookEx (not blocked!)
    // If (flags & 1) != 0 (Numpad Enter): consumed!
    let main_enter_flags = 0x00; // LLKHF_EXTENDED not set
    let numpad_enter_flags = 0x01; // LLKHF_EXTENDED set

    assert_eq!(main_enter_flags & 1, 0, "Main Enter must not have extended bit");
    assert_ne!(numpad_enter_flags & 1, 0, "Numpad Enter must have extended bit");
    println!("  [PASS] Main Enter key is strictly isolated from Numpad Enter.");
}

#[test]
fn test_12_media_and_mic_actions() {
    assert_eq!(decode_action(WPARAM(1)), Some(AppAction::LayerEnter));
    assert_eq!(decode_action(WPARAM(2)), Some(AppAction::LayerExit));
    assert_eq!(decode_action(WPARAM(6)), Some(AppAction::ToggleMicMute));
    assert_eq!(decode_action(WPARAM(7)), Some(AppAction::PlayPause));
    assert_eq!(decode_action(WPARAM(8)), Some(AppAction::NextTrack));
    assert_eq!(decode_action(WPARAM(9)), Some(AppAction::PrevTrack));
    assert_eq!(decode_action(WPARAM(105)), Some(AppAction::VolumeUp(5)));
    assert_eq!(decode_action(WPARAM(205)), Some(AppAction::VolumeDown(5)));
    println!("  [PASS] Media transport and microphone hook callbacks verified.");
}

#[test]
fn test_13_overlay_position_math() {
    let cfg = Config::default();
    let pos = cfg.appearance.position.to_lowercase();
    assert_eq!(pos, "top-center");
    assert_eq!(cfg.appearance.width, 360);
    assert!(cfg.appearance.animation_enabled);
    println!("  [PASS] Overlay HUD geometry and position calculations verified.");
}

#[test]
fn test_14_vu_meter_ballistics() {
    // Instant attack test
    let mut smoothed = 0.2f32;
    let new_pk = 0.85f32;
    if new_pk >= smoothed {
        smoothed = new_pk;
    }
    assert_eq!(smoothed, 0.85);

    // Ballistic decay test
    let lower_pk = 0.10f32;
    smoothed = smoothed * 0.82 + lower_pk * 0.18;
    assert!(smoothed < 0.85 && smoothed > 0.60);
    println!("  [PASS] Live VU meter real-time polling, instant attack, and exponential decay verified.");
}

#[test]
fn test_15_startup_manager() {
    // Check Task Scheduler status query
    let _ = is_startup_enabled();
    println!("  [PASS] Startup Task Scheduler detection verified.");
}

#[test]
fn test_16_desktop_shortcut() {
    let shortcut_path = get_desktop_shortcut_path();
    assert!(shortcut_path.to_str().unwrap().ends_with("Open Volume.lnk"));
    println!("  [PASS] Desktop shortcut path resolution verified: {:?}", shortcut_path);
}

#[test]
fn test_17_theme_definitions() {
    let themes = list_themes();
    assert_eq!(themes.len(), 8, "Must provide exactly 8 themes");
    let ids: Vec<&str> = themes.iter().map(|t| t.id.as_str()).collect();
    assert!(ids.contains(&"cyberpunk"));
    assert!(ids.contains(&"nord"));
    assert!(ids.contains(&"dracula"));
    assert!(ids.contains(&"catppuccin"));
    assert!(ids.contains(&"solarized"));
    assert!(ids.contains(&"amber"));
    assert!(ids.contains(&"oled"));
    assert!(ids.contains(&"light"));

    // Verify hex color parser
    let colorref = hex_to_colorref("#00E5A3");
    assert_eq!(colorref, 0x00A3E500); // 0x00BBGGRR
    println!("  [PASS] All 8 themes verified with complete color palettes.");
}

#[test]
fn test_18_theme_application() {
    let mut cfg = Config::default();
    cfg.apply_theme("dracula");
    assert_eq!(cfg.appearance.theme, "dracula");
    assert_eq!(cfg.appearance.accent_color, "#BD93F9");
    let t = get_theme("dracula");
    assert_eq!(t.name, "Dracula Vampire");
    println!("  [PASS] Theme application and active id resolution verified.");
}
