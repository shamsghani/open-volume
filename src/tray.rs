use crate::config::{list_themes, Config};
use crate::startup::is_startup_enabled;
use std::sync::{Arc, Mutex};
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::UI::Shell::*;
use windows::Win32::UI::WindowsAndMessaging::*;

pub const WM_APP_TRAY: u32 = WM_USER + 2;

pub const ID_TRAY_STATUS: u32 = 1000;
pub const ID_TRAY_TOGGLE_LAYER: u32 = 1001;
pub const ID_TRAY_MUTE_MIC: u32 = 1002;
pub const ID_TRAY_SETTINGS: u32 = 1003;
pub const ID_TRAY_STARTUP: u32 = 1004;
pub const ID_TRAY_SHORTCUT: u32 = 1005;
pub const ID_TRAY_EXIT: u32 = 1006;

pub const ID_TRAY_THEME_BASE: u32 = 2000;
pub const ID_TRAY_PROFILE_BASE: u32 = 3000;
pub const ID_TRAY_POS_BASE: u32 = 4000;

pub struct TrayIcon {
    hwnd: HWND,
    nid: NOTIFYICONDATAW,
    config: Arc<Mutex<Config>>,
}

impl TrayIcon {
    pub fn new(hwnd: HWND, config: Arc<Mutex<Config>>) -> Self {
        let mut nid = NOTIFYICONDATAW {
            cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32,
            hWnd: hwnd,
            uID: 1,
            uFlags: NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage: WM_APP_TRAY,
            hIcon: create_tray_icon(false),
            ..Default::default()
        };

        let tip = "Open-Volume: Audio Mixer";
        let h_tip = HSTRING::from(tip);
        let wide = h_tip.as_wide();
        let len = wide.len().min(nid.szTip.len() - 1);
        nid.szTip[..len].copy_from_slice(&wide[..len]);
        nid.szTip[len] = 0;

        unsafe {
            let _ = Shell_NotifyIconW(NIM_ADD, &nid);
        }

        Self { hwnd, nid, config }
    }

    pub fn set_active_state(&mut self, active: bool) {
        unsafe {
            if !self.nid.hIcon.0.is_null() {
                let _ = DestroyIcon(self.nid.hIcon);
            }
            self.nid.hIcon = create_tray_icon(active);
            let _ = Shell_NotifyIconW(NIM_MODIFY, &self.nid);
        }
    }

    pub fn show_menu(&self, active_layer: bool, mic_muted: bool) {
        unsafe {
            let menu = match CreatePopupMenu() {
                Ok(m) => m,
                Err(_) => return,
            };

            // 1. Title Item (disabled)
            let status_str = if active_layer { "Open Volume: ACTIVE" } else { "Open Volume: READY" };
            let h_status = HSTRING::from(status_str);
            let _ = AppendMenuW(menu, MF_STRING | MF_DISABLED | MF_GRAYED, ID_TRAY_STATUS as usize, PCWSTR(h_status.as_ptr()));
            let _ = AppendMenuW(menu, MF_SEPARATOR, 0, None);

            // 2. Quick Actions
            let _ = AppendMenuW(menu, MF_STRING, ID_TRAY_TOGGLE_LAYER as usize, w!("Toggle HUD Layer"));

            let mic_flags = if mic_muted { MF_STRING | MF_CHECKED } else { MF_STRING };
            let _ = AppendMenuW(menu, mic_flags, ID_TRAY_MUTE_MIC as usize, w!("Mute Microphone"));

            let _ = AppendMenuW(menu, MF_SEPARATOR, 0, None);

            // 3. Themes Submenu
            if let Ok(theme_menu) = CreatePopupMenu() {
                let current_theme = self.config.lock().unwrap().appearance.theme.clone();
                for (i, t) in list_themes().iter().enumerate() {
                    let mut flags = MF_STRING;
                    if t.id.eq_ignore_ascii_case(&current_theme) {
                        flags |= MF_CHECKED;
                    }
                    let label = format!("{}  {}", t.emoji, t.name);
                    let h_label = HSTRING::from(label.as_str());
                    let _ = AppendMenuW(theme_menu, flags, (ID_TRAY_THEME_BASE + i as u32) as usize, PCWSTR(h_label.as_ptr()));
                }
                let _ = AppendMenuW(menu, MF_POPUP, theme_menu.0 as usize, w!("Themes"));
            }

            // 4. Profiles Submenu
            if let Ok(prof_menu) = CreatePopupMenu() {
                let profiles = [
                    (0, "🎮  Gaming Mode"),
                    (1, "🎧  Focus / Work"),
                    (2, "🍿  Cinema / Movie"),
                ];
                for (i, label) in profiles {
                    let h_label = HSTRING::from(label);
                    let _ = AppendMenuW(prof_menu, MF_STRING, (ID_TRAY_PROFILE_BASE + i) as usize, PCWSTR(h_label.as_ptr()));
                }
                let _ = AppendMenuW(menu, MF_POPUP, prof_menu.0 as usize, w!("Audio Profiles"));
            }

            // 5. Positions Submenu
            if let Ok(pos_menu) = CreatePopupMenu() {
                let current_pos = self.config.lock().unwrap().appearance.position.clone();
                let positions = [
                    ("bottom-right", "Bottom-Right"),
                    ("top-center", "Top-Center"),
                    ("top-right", "Top-Right"),
                    ("bottom-center", "Bottom-Center"),
                ];
                for (i, (pos_id, label)) in positions.iter().enumerate() {
                    let mut flags = MF_STRING;
                    if pos_id.eq_ignore_ascii_case(&current_pos) {
                        flags |= MF_CHECKED;
                    }
                    let h_label = HSTRING::from(*label);
                    let _ = AppendMenuW(pos_menu, flags, (ID_TRAY_POS_BASE + i as u32) as usize, PCWSTR(h_label.as_ptr()));
                }
                let _ = AppendMenuW(menu, MF_POPUP, pos_menu.0 as usize, w!("HUD Position"));
            }

            let _ = AppendMenuW(menu, MF_SEPARATOR, 0, None);

            // 6. Settings & Boot
            let _ = AppendMenuW(menu, MF_STRING, ID_TRAY_SETTINGS as usize, w!("Settings..."));

            let startup_enabled = is_startup_enabled();
            let boot_flags = if startup_enabled { MF_STRING | MF_CHECKED } else { MF_STRING };
            let _ = AppendMenuW(menu, boot_flags, ID_TRAY_STARTUP as usize, w!("Start on Windows Boot"));

            let _ = AppendMenuW(menu, MF_STRING, ID_TRAY_SHORTCUT as usize, w!("Create Desktop Shortcut"));

            let _ = AppendMenuW(menu, MF_SEPARATOR, 0, None);
            let _ = AppendMenuW(menu, MF_STRING, ID_TRAY_EXIT as usize, w!("Exit"));

            let mut pt = POINT::default();
            let _ = GetCursorPos(&mut pt);
            let _ = SetForegroundWindow(self.hwnd);
            let _ = TrackPopupMenuEx(menu, (TPM_RIGHTALIGN | TPM_BOTTOMALIGN).0, pt.x, pt.y, self.hwnd, None);
            let _ = DestroyMenu(menu);
        }
    }
}

impl Drop for TrayIcon {
    fn drop(&mut self) {
        unsafe {
            let _ = Shell_NotifyIconW(NIM_DELETE, &self.nid);
            if !self.nid.hIcon.0.is_null() {
                let _ = DestroyIcon(self.nid.hIcon);
            }
        }
    }
}

fn create_tray_icon(active: bool) -> HICON {
    unsafe {
        let size = 32;
        let hdc = GetDC(None);
        let mem_dc = CreateCompatibleDC(hdc);
        let color_bm = CreateCompatibleBitmap(hdc, size, size);
        let mask_bm = CreateCompatibleBitmap(hdc, size, size);

        let old_bm = SelectObject(mem_dc, color_bm);

        // Draw icon background (dark round rect)
        let bg_brush = CreateSolidBrush(COLORREF(0x00181312));
        SelectObject(mem_dc, bg_brush);
        RoundRect(mem_dc, 2, 2, size - 2, size - 2, 8, 8);

        // Draw volume speaker glyph
        let spk_brush = CreateSolidBrush(COLORREF(0x00FFFFFF));
        SelectObject(mem_dc, spk_brush);
        RoundRect(mem_dc, 8, 12, 14, 20, 3, 3);
        DeleteObject(spk_brush);

        // Active green badge dot if Layer 2 is active
        if active {
            let dot_brush = CreateSolidBrush(COLORREF(0x00A3E500)); // Bright emerald green
            SelectObject(mem_dc, dot_brush);
            Ellipse(mem_dc, size - 11, 3, size - 3, 11);
            DeleteObject(dot_brush);
        }

        SelectObject(mem_dc, old_bm);
        DeleteObject(bg_brush);
        DeleteDC(mem_dc);
        ReleaseDC(None, hdc);

        let icon_info = ICONINFO {
            fIcon: true.into(),
            xHotspot: 0,
            yHotspot: 0,
            hbmMask: mask_bm,
            hbmColor: color_bm,
        };

        let hicon = CreateIconIndirect(&icon_info).unwrap_or(HICON(std::ptr::null_mut()));
        DeleteObject(color_bm);
        DeleteObject(mask_bm);

        hicon
    }
}
