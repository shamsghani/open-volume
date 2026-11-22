#![windows_subsystem = "windows"]
#![allow(unused_must_use, dead_code, static_mut_refs, unused_assignments)]

mod audio;
mod config;
mod hook;
mod overlay;
mod settings;
mod sound;
mod startup;
mod tray;

pub fn log_event(msg: &str) {
    let log_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("open_volume.log")))
        .unwrap_or_else(|| std::path::PathBuf::from("open_volume.log"));
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(log_path) {
        use std::io::Write;
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let _ = writeln!(f, "[{}] {}", ts, msg);
    }
}

use audio::AudioMixer;
use config::{list_themes, Config};
use hook::{decode_action, AppAction, KeyboardHook, WM_APP_ACTION};
use overlay::OverlayWindow;
use settings::SettingsWindow;
use startup::ensure_admin_elevation;
use std::sync::{Arc, Mutex};
use tray::{
    TrayIcon, ID_TRAY_EXIT, ID_TRAY_MUTE_MIC, ID_TRAY_POS_BASE, ID_TRAY_PROFILE_BASE,
    ID_TRAY_SETTINGS, ID_TRAY_SHORTCUT, ID_TRAY_STARTUP, ID_TRAY_THEME_BASE,
    ID_TRAY_TOGGLE_LAYER, WM_APP_TRAY,
};
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::System::Threading::*;
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::WindowsAndMessaging::*;

const MUTEX_NAME: PCWSTR = w!("Local\\MountainEverest60_NumpadAudioLayer_SingleInstance");

struct AppState {
    config: Arc<Mutex<Config>>,
    mixer: Arc<Mutex<AudioMixer>>,
    overlay: Box<OverlayWindow>,
    settings: Box<SettingsWindow>,
    tray: Option<TrayIcon>,
}

static mut APP_STATE: Option<AppState> = None;
static mut WM_TASKBAR_CREATED: u32 = 0;

fn main() {
    log_event("Starting Open-Volume...");
    // 1. Silent Administrator Elevation Check (to bypass UIPI over games like Tiny Glade)
    ensure_admin_elevation();
    log_event("Admin elevation checked / passed");

    // 2. Single-Instance Enforcement via Named Mutex
    unsafe {
        let _ = CreateMutexW(None, false, MUTEX_NAME);
        if GetLastError() == ERROR_ALREADY_EXISTS {
            log_event("Instance already exists, exiting");
            std::process::exit(0);
        }
    }
    log_event("Single-instance mutex acquired");

    // 3. Load Configuration
    let config = Arc::new(Mutex::new(Config::load()));
    let (perceptual, pinned) = {
        let cfg = config.lock().unwrap();
        (cfg.volume.perceptual_curve, cfg.pinned_apps.clone())
    };

    // 4. Initialize Core Audio Mixer
    let mixer = Arc::new(Mutex::new(AudioMixer::new(perceptual, pinned)));

    // 5. Create Hidden Message Receiver Window
    let main_hwnd = create_message_window();
    log_event(&format!("create_message_window returned: {:?}", main_hwnd));

    // 6. Create HUD Overlay & Settings Windows
    let overlay = OverlayWindow::new(main_hwnd, Arc::clone(&config), Arc::clone(&mixer));
    let settings = SettingsWindow::new(Arc::clone(&config));

    // 7. Create System Tray Icon
    let tray = TrayIcon::new(main_hwnd, Arc::clone(&config));

    unsafe {
        APP_STATE = Some(AppState {
            config: Arc::clone(&config),
            mixer: Arc::clone(&mixer),
            overlay,
            settings,
            tray: Some(tray),
        });
    }

    // 8. Install Low-Level Keyboard Hook
    let initial_cfg = config.lock().unwrap().clone();
    KeyboardHook::install(main_hwnd, initial_cfg);

    // 9. Main Win32 Event Loop
    unsafe {
        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).as_bool() {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }

    // Clean up
    KeyboardHook::uninstall();
}

fn create_message_window() -> HWND {
    unsafe {
        let hinst: HINSTANCE = GetModuleHandleW(None).unwrap_or_default().into();
        let class_name = w!("OpenVolumeMainMsgClass");
        let wnd_class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            lpfnWndProc: Some(main_wnd_proc),
            hInstance: hinst,
            lpszClassName: PCWSTR(class_name.as_ptr()),
            ..Default::default()
        };

        RegisterClassExW(&wnd_class);

        let hwnd = CreateWindowExW(
            WINDOW_EX_STYLE(0),
            PCWSTR(class_name.as_ptr()),
            w!("OpenVolumeMainMsgReceiver"),
            WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            hinst,
            None,
        ).unwrap_or(HWND(std::ptr::null_mut()));

        // Register TaskbarCreated message and allow through UIPI filter so elevated app receives it
        WM_TASKBAR_CREATED = RegisterWindowMessageW(w!("TaskbarCreated"));
        if WM_TASKBAR_CREATED != 0 {
            let _ = ChangeWindowMessageFilter(WM_TASKBAR_CREATED, MSGFLT_ADD);
        }
        let _ = ChangeWindowMessageFilter(WM_APP_TRAY, MSGFLT_ADD);
        let _ = ChangeWindowMessageFilter(WM_COMMAND, MSGFLT_ADD);

        hwnd
    }
}

unsafe extern "system" fn main_wnd_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    if msg == WM_TASKBAR_CREATED && WM_TASKBAR_CREATED != 0 {
        log_event("Received TaskbarCreated broadcast from Explorer! Re-registering tray icon...");
        if let Some(ref mut state) = APP_STATE {
            if let Some(ref mut tray) = state.tray {
                tray.add_or_update();
            }
        }
        return LRESULT(0);
    }

    match msg {
        WM_TIMER => {
            if wparam.0 == tray::TIMER_TRAY_RETRY {
                if let Some(ref mut state) = APP_STATE {
                    if let Some(ref mut tray) = state.tray {
                        if tray.add_or_update() {
                            let _ = KillTimer(hwnd, tray::TIMER_TRAY_RETRY);
                        }
                    }
                }
            }
            LRESULT(0)
        }
        WM_APP_ACTION => {
            if let Some(action) = decode_action(wparam) {
                handle_app_action(action);
            }
            LRESULT(0)
        }
        WM_APP_TRAY => {
            let event = (lparam.0 & 0xFFFF) as u32;
            let icon_id = ((lparam.0 >> 16) & 0xFFFF) as u32;
            if event != WM_MOUSEMOVE {
                log_event(&format!(
                    "WM_APP_TRAY: event = 0x{:04X} ({}), icon_id = {}",
                    event, event, icon_id
                ));
            }
            if event == WM_RBUTTONUP || event == WM_CONTEXTMENU {
                let x = (wparam.0 & 0xFFFF) as i16 as i32;
                let y = ((wparam.0 >> 16) & 0xFFFF) as i16 as i32;
                let pos = if x != 0 || y != 0 { Some((x, y)) } else { None };
                if let Some(ref mut state) = APP_STATE {
                    let mic_muted = state.mixer.lock().unwrap().get_microphone_info().2;
                    if let Some(ref tray) = state.tray {
                        tray.show_menu(KeyboardHook::is_layer_active(), mic_muted, pos);
                    }
                }
            } else if event == WM_LBUTTONUP
                || event == 0x0400 /* NIN_SELECT */
                || event == 0x0401 /* NIN_KEYSELECT */
            {
                let cur = KeyboardHook::is_layer_active();
                KeyboardHook::set_layer_active(!cur);
                handle_app_action(if !cur { AppAction::LayerEnter } else { AppAction::LayerExit });
            }
            LRESULT(0)
        }
        WM_COMMAND => {
            let cmd_id = (wparam.0 & 0xFFFF) as u32;
            handle_tray_command(cmd_id);
            LRESULT(0)
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

fn handle_app_action(action: AppAction) {
    log_event(&format!("Action triggered: {:?}", action));
    unsafe {
        let state = match APP_STATE.as_mut() {
            Some(s) => s,
            None => return,
        };

        let sound_enabled = state.config.lock().unwrap().volume.sound_feedback;

        match action {
            AppAction::LayerEnter => {
                KeyboardHook::set_layer_active(true);
                {
                    let mut mixer = state.mixer.lock().unwrap();
                    mixer.refresh();
                    let follow = state.config.lock().unwrap().behavior.follow_focus;
                    if follow {
                        mixer.auto_select_foreground_app();
                    }
                }
                state.overlay.show();
                if let Some(ref mut tray) = state.tray {
                    tray.set_active_state(true);
                }
                if sound_enabled { sound::play_layer_on(); }
            }
            AppAction::LayerExit => {
                let was_active = KeyboardHook::is_layer_active();
                KeyboardHook::set_layer_active(false);
                state.overlay.hide();
                if let Some(ref mut tray) = state.tray {
                    tray.set_active_state(false);
                }
                if was_active && sound_enabled { sound::play_layer_off(); }
            }
            AppAction::VolumeUp(step) => {
                state.mixer.lock().unwrap().adjust_volume(step);
                state.overlay.update_display();
                if sound_enabled { sound::play_volume_up(); }
            }
            AppAction::VolumeDown(step) => {
                state.mixer.lock().unwrap().adjust_volume(-step);
                state.overlay.update_display();
                if sound_enabled { sound::play_volume_down(); }
            }
            AppAction::SelectNext => {
                state.mixer.lock().unwrap().select_next();
                state.overlay.update_display();
                if sound_enabled { sound::play_cycle(); }
            }
            AppAction::SelectPrev => {
                state.mixer.lock().unwrap().select_prev();
                state.overlay.update_display();
                if sound_enabled { sound::play_cycle(); }
            }
            AppAction::ToggleMute => {
                state.mixer.lock().unwrap().toggle_mute();
                state.overlay.update_display();
                if sound_enabled { sound::play_mute(); }
            }
            AppAction::SelectIndex(idx) => {
                state.mixer.lock().unwrap().select_index(idx);
                state.overlay.update_display();
                if sound_enabled { sound::play_cycle(); }
            }
            AppAction::ToggleMicMute => {
                let muted = state.mixer.lock().unwrap().toggle_microphone_mute();
                let msg = if muted { "All Microphones MUTED" } else { "All Microphones LIVE" };
                state.overlay.show_toast(msg, "🎙️");
                state.overlay.update_display();
                if sound_enabled { sound::play_mute(); }
            }
            AppAction::PlayPause => {
                simulate_media_key(VK_MEDIA_PLAY_PAUSE);
                state.overlay.show_toast("Play / Pause", "⏯");
                if sound_enabled { sound::play_cycle(); }
            }
            AppAction::NextTrack => {
                simulate_media_key(VK_MEDIA_NEXT_TRACK);
                state.overlay.show_toast("Next Track", "⏭");
                if sound_enabled { sound::play_cycle(); }
            }
            AppAction::PrevTrack => {
                simulate_media_key(VK_MEDIA_PREV_TRACK);
                state.overlay.show_toast("Previous Track", "⏮");
                if sound_enabled { sound::play_cycle(); }
            }
        }
    }
}

fn simulate_media_key(vk: VIRTUAL_KEY) {
    unsafe {
        keybd_event(vk.0 as u8, 0, KEYBD_EVENT_FLAGS(0), 0);
        keybd_event(vk.0 as u8, 0, KEYEVENTF_KEYUP, 0);
    }
}

fn handle_tray_command(cmd_id: u32) {
    unsafe {
        let state = match APP_STATE.as_mut() {
            Some(s) => s,
            None => return,
        };

        match cmd_id {
            ID_TRAY_TOGGLE_LAYER => {
                let cur = KeyboardHook::is_layer_active();
                KeyboardHook::set_layer_active(!cur);
                handle_app_action(if !cur { AppAction::LayerEnter } else { AppAction::LayerExit });
            }
            ID_TRAY_MUTE_MIC => {
                handle_app_action(AppAction::ToggleMicMute);
            }
            ID_TRAY_SETTINGS => {
                state.settings.show();
            }
            ID_TRAY_STARTUP => {
                let cur = startup::is_startup_enabled();
                let _ = startup::set_startup_enabled(!cur);
                state.config.lock().unwrap().behavior.start_on_boot = !cur;
                state.config.lock().unwrap().save();
            }
            ID_TRAY_SHORTCUT => {
                startup::create_desktop_shortcut();
            }
            ID_TRAY_EXIT => {
                PostQuitMessage(0);
            }
            ID_TRAY_THEME_BASE..=2015 => {
                let idx = (cmd_id - ID_TRAY_THEME_BASE) as usize;
                let themes = list_themes();
                if let Some(t) = themes.get(idx) {
                    let mut cfg = state.config.lock().unwrap();
                    cfg.apply_theme(&t.id);
                    cfg.save();
                    state.overlay.update_display();
                }
            }
            ID_TRAY_PROFILE_BASE..=3005 => {
                let idx = cmd_id - ID_TRAY_PROFILE_BASE;
                let pkey = match idx {
                    0 => "gaming",
                    1 => "focus",
                    2 => "cinema",
                    _ => "",
                };
                if !pkey.is_empty() {
                    let (prof, name, emoji) = {
                        let cfg = state.config.lock().unwrap();
                        let p = cfg.profiles.get(pkey).cloned();
                        match p {
                            Some(prof) => (Some(prof.clone()), prof.name, prof.emoji),
                            None => (None, String::new(), String::new()),
                        }
                    };
                    if let Some(p) = prof {
                        state.mixer.lock().unwrap().apply_profile(&p);
                        let toast = format!("Profile: {}", name);
                        state.overlay.show_toast(&toast, &emoji);
                        state.overlay.update_display();
                    }
                }
            }
            ID_TRAY_POS_BASE..=4005 => {
                let idx = cmd_id - ID_TRAY_POS_BASE;
                let pos = match idx {
                    0 => "bottom-right",
                    1 => "top-center",
                    2 => "top-right",
                    3 => "bottom-center",
                    _ => "",
                };
                if !pos.is_empty() {
                    let mut cfg = state.config.lock().unwrap();
                    cfg.appearance.position = pos.to_string();
                    cfg.save();
                    state.overlay.update_display();
                }
            }
            _ => {}
        }
    }
}
