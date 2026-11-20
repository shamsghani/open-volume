use crate::config::Config;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use windows::Win32::Foundation::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::WindowsAndMessaging::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppAction {
    LayerEnter,
    LayerExit,
    VolumeUp(i32),
    VolumeDown(i32),
    SelectNext,
    SelectPrev,
    ToggleMute,
    SelectIndex(usize),
    ToggleMicMute,
    PlayPause,
    NextTrack,
    PrevTrack,
}

static LAYER_ACTIVE: AtomicBool = AtomicBool::new(false);
static CTRL_DOWN: AtomicBool = AtomicBool::new(false);
static ALT_DOWN: AtomicBool = AtomicBool::new(false);
static SHIFT_DOWN: AtomicBool = AtomicBool::new(false);
static WIN_DOWN: AtomicBool = AtomicBool::new(false);

static mut HOOK_HANDLE: HHOOK = HHOOK(std::ptr::null_mut());
static mut MAIN_HWND: HWND = HWND(std::ptr::null_mut());
static LAST_NUMLOCK_TIME: Mutex<Option<Instant>> = Mutex::new(None);
static CONFIG_CACHE: Mutex<Option<Config>> = Mutex::new(None);

pub const WM_APP_ACTION: u32 = WM_USER + 100;

pub struct KeyboardHook;

impl KeyboardHook {
    pub fn install(main_hwnd: HWND, config: Config) -> bool {
        unsafe {
            MAIN_HWND = main_hwnd;
            *CONFIG_CACHE.lock().unwrap() = Some(config);

            let hinst: HINSTANCE = GetModuleHandleW(None).unwrap_or_default().into();
            let hook = SetWindowsHookExW(
                WH_KEYBOARD_LL,
                Some(low_level_keyboard_proc),
                hinst,
                0,
            );

            if let Ok(h) = hook {
                HOOK_HANDLE = h;
                true
            } else {
                false
            }
        }
    }

    pub fn uninstall() {
        unsafe {
            if !HOOK_HANDLE.0.is_null() {
                let _ = UnhookWindowsHookEx(HOOK_HANDLE);
                HOOK_HANDLE = HHOOK(std::ptr::null_mut());
            }
        }
    }

    pub fn is_layer_active() -> bool {
        LAYER_ACTIVE.load(Ordering::SeqCst)
    }

    pub fn set_layer_active(active: bool) {
        LAYER_ACTIVE.store(active, Ordering::SeqCst);
    }

    pub fn update_config(config: Config) {
        if let Ok(mut c) = CONFIG_CACHE.lock() {
            *c = Some(config);
        }
    }
}

fn dispatch(action: AppAction) {
    unsafe {
        if !MAIN_HWND.0.is_null() {
            let action_id = match action {
                AppAction::LayerEnter => 1,
                AppAction::LayerExit => 2,
                AppAction::VolumeUp(step) => 100 + step as usize,
                AppAction::VolumeDown(step) => 200 + step as usize,
                AppAction::SelectNext => 3,
                AppAction::SelectPrev => 4,
                AppAction::ToggleMute => 5,
                AppAction::SelectIndex(idx) => 300 + idx,
                AppAction::ToggleMicMute => 6,
                AppAction::PlayPause => 7,
                AppAction::NextTrack => 8,
                AppAction::PrevTrack => 9,
            };
            let _ = PostMessageW(MAIN_HWND, WM_APP_ACTION, WPARAM(action_id), LPARAM(0));
        }
    }
}

pub fn decode_action(wparam: WPARAM) -> Option<AppAction> {
    let val = wparam.0;
    match val {
        1 => Some(AppAction::LayerEnter),
        2 => Some(AppAction::LayerExit),
        3 => Some(AppAction::SelectNext),
        4 => Some(AppAction::SelectPrev),
        5 => Some(AppAction::ToggleMute),
        6 => Some(AppAction::ToggleMicMute),
        7 => Some(AppAction::PlayPause),
        8 => Some(AppAction::NextTrack),
        9 => Some(AppAction::PrevTrack),
        100..=199 => Some(AppAction::VolumeUp((val - 100) as i32)),
        200..=299 => Some(AppAction::VolumeDown((val - 200) as i32)),
        300..=399 => Some(AppAction::SelectIndex(val - 300)),
        _ => None,
    }
}

unsafe extern "system" fn low_level_keyboard_proc(
    n_code: i32,
    w_param: WPARAM,
    l_param: LPARAM,
) -> LRESULT {
    if n_code >= 0 {
        let kb = *(l_param.0 as *const KBDLLHOOKSTRUCT);
        let msg = w_param.0 as u32;
        let vk = kb.vkCode;
        let is_down = msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN;
        let _is_up = msg == WM_KEYUP || msg == WM_SYSKEYUP;
        let is_extended = (kb.flags.0 & 1) != 0;

        // Track modifiers
        match VIRTUAL_KEY(vk as u16) {
            VK_CONTROL | VK_LCONTROL | VK_RCONTROL => CTRL_DOWN.store(is_down, Ordering::SeqCst),
            VK_MENU | VK_LMENU | VK_RMENU => ALT_DOWN.store(is_down, Ordering::SeqCst),
            VK_SHIFT | VK_LSHIFT | VK_RSHIFT => SHIFT_DOWN.store(is_down, Ordering::SeqCst),
            VK_LWIN | VK_RWIN => WIN_DOWN.store(is_down, Ordering::SeqCst),
            _ => {}
        }

        let ctrl = CTRL_DOWN.load(Ordering::SeqCst);
        let alt = ALT_DOWN.load(Ordering::SeqCst);
        let shift = SHIFT_DOWN.load(Ordering::SeqCst);
        let win = WIN_DOWN.load(Ordering::SeqCst);
        let active = LAYER_ACTIVE.load(Ordering::SeqCst);

        let cfg = CONFIG_CACHE.lock().unwrap().clone().unwrap_or_default();
        let step = cfg.volume.step_percent;
        let fine_step = cfg.volume.fine_step_percent;

        // 1. Check custom toggle shortcut (e.g. Ctrl + Alt + V)
        if is_down {
            if let Some(toggle_binding) = cfg.custom_bindings.get("toggle_layer") {
                if toggle_binding.vk == vk
                    && toggle_binding.ctrl == ctrl
                    && toggle_binding.alt == alt
                    && toggle_binding.shift == shift
                    && toggle_binding.win == win
                {
                    if active {
                        LAYER_ACTIVE.store(false, Ordering::SeqCst);
                        dispatch(AppAction::LayerExit);
                    } else {
                        LAYER_ACTIVE.store(true, Ordering::SeqCst);
                        dispatch(AppAction::LayerEnter);
                    }
                    return LRESULT(1);
                }
            }
        }

        // 2. Check NumLock triggers
        if vk == VK_NUMLOCK.0 as u32 && is_down {
            // A. Ctrl + NumLock
            if ctrl && cfg.hotkey.ctrl_numlock {
                if active {
                    LAYER_ACTIVE.store(false, Ordering::SeqCst);
                    dispatch(AppAction::LayerExit);
                } else {
                    LAYER_ACTIVE.store(true, Ordering::SeqCst);
                    dispatch(AppAction::LayerEnter);
                }
                return LRESULT(1);
            }

            // B. Double-tap NumLock
            if cfg.hotkey.double_tap_numlock {
                let now = Instant::now();
                let mut last = LAST_NUMLOCK_TIME.lock().unwrap();
                if let Some(prev) = *last {
                    if now.duration_since(prev) <= Duration::from_millis(cfg.hotkey.double_tap_max_interval_ms) {
                        *last = None;
                        if active {
                            LAYER_ACTIVE.store(false, Ordering::SeqCst);
                            dispatch(AppAction::LayerExit);
                        } else {
                            LAYER_ACTIVE.store(true, Ordering::SeqCst);
                            dispatch(AppAction::LayerEnter);
                        }
                        return LRESULT(1);
                    }
                }
                *last = Some(now);
            }

            // If already in Layer 2, pressing NumLock exits Layer 2
            if active {
                LAYER_ACTIVE.store(false, Ordering::SeqCst);
                dispatch(AppAction::LayerExit);
                return LRESULT(1);
            }
        }

        // 3. When Layer 2 is ACTIVE: handle numpad & macro keys
        if active {
            // Strictly isolate Main Enter from Numpad Enter
            if vk == VK_RETURN.0 as u32 {
                if !is_extended {
                    // Main Enter! Never block! Pass through transparently to games and apps!
                    return CallNextHookEx(HOOK_HANDLE, n_code, w_param, l_param);
                }
                // Numpad Enter: consume or toggle
                if is_down {
                    dispatch(AppAction::SelectNext);
                }
                return LRESULT(1);
            }

            // Escape exits Layer 2
            if vk == VK_ESCAPE.0 as u32 {
                if is_down {
                    LAYER_ACTIVE.store(false, Ordering::SeqCst);
                    dispatch(AppAction::LayerExit);
                }
                return LRESULT(1);
            }

            // Media keys on Numpad
            if cfg.behavior.numpad_media_keys {
                if vk == VK_NUMPAD7.0 as u32 && is_down {
                    dispatch(AppAction::PrevTrack);
                    return LRESULT(1);
                }
                if vk == VK_NUMPAD9.0 as u32 && is_down {
                    dispatch(AppAction::NextTrack);
                    return LRESULT(1);
                }
                if vk == VK_NUMPAD3.0 as u32 && is_down {
                    dispatch(AppAction::PlayPause);
                    return LRESULT(1);
                }
            }

            // Microphone mute toggle
            if (vk == VK_DECIMAL.0 as u32 || vk == 0x4D && ctrl && alt) && is_down {
                dispatch(AppAction::ToggleMicMute);
                return LRESULT(1);
            }

            // Volume controls
            if vk == VK_ADD.0 as u32 { // Numpad +
                if is_down { dispatch(AppAction::VolumeUp(step)); }
                return LRESULT(1);
            }
            if vk == VK_SUBTRACT.0 as u32 { // Numpad -
                if is_down { dispatch(AppAction::VolumeDown(step)); }
                return LRESULT(1);
            }
            if vk == VK_MULTIPLY.0 as u32 { // Numpad * (fine up)
                if is_down { dispatch(AppAction::VolumeUp(fine_step)); }
                return LRESULT(1);
            }
            if vk == VK_DIVIDE.0 as u32 { // Numpad / (fine down)
                if is_down { dispatch(AppAction::VolumeDown(fine_step)); }
                return LRESULT(1);
            }

            // App cycling
            if vk == VK_NUMPAD8.0 as u32 || vk == VK_UP.0 as u32 {
                if is_down { dispatch(AppAction::SelectPrev); }
                return LRESULT(1);
            }
            if vk == VK_NUMPAD2.0 as u32 || vk == VK_DOWN.0 as u32 {
                if is_down { dispatch(AppAction::SelectNext); }
                return LRESULT(1);
            }
            if vk == VK_NUMPAD4.0 as u32 || vk == VK_LEFT.0 as u32 {
                if is_down { dispatch(AppAction::SelectPrev); }
                return LRESULT(1);
            }
            if vk == VK_NUMPAD6.0 as u32 || vk == VK_RIGHT.0 as u32 {
                if is_down { dispatch(AppAction::SelectNext); }
                return LRESULT(1);
            }

            // Mute toggle (Numpad 5 or 'M')
            if vk == VK_NUMPAD5.0 as u32 || vk == 0x4D && !ctrl && !alt {
                if is_down { dispatch(AppAction::ToggleMute); }
                return LRESULT(1);
            }

            // Numpad 0 -> Master volume (index 0)
            if vk == VK_NUMPAD0.0 as u32 {
                if is_down { dispatch(AppAction::SelectIndex(0)); }
                return LRESULT(1);
            }

            // Numpad 1..9 direct index selection
            if (VK_NUMPAD1.0 as u32..=VK_NUMPAD9.0 as u32).contains(&vk) && !cfg.behavior.numpad_media_keys {
                let idx = (vk - VK_NUMPAD1.0 as u32 + 1) as usize;
                if is_down { dispatch(AppAction::SelectIndex(idx)); }
                return LRESULT(1);
            }
        }
    }

    CallNextHookEx(HOOK_HANDLE, n_code, w_param, l_param)
}
