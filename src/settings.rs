use crate::config::{hex_to_colorref, list_themes, BindingConfig, Config};
use crate::startup::{is_startup_enabled, set_startup_enabled};
use std::sync::{Arc, Mutex};
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::Shell::*;
use windows::Win32::UI::WindowsAndMessaging::*;

const BINDING_ACTIONS: &[(&str, &str)] = &[
    ("toggle_layer", "Toggle HUD Layer"),
    ("volume_up", "Volume Up (+)"),
    ("volume_down", "Volume Down (-)"),
    ("next_app", "Next App"),
    ("prev_app", "Previous App"),
    ("toggle_mute", "Toggle Mute"),
    ("toggle_mic_mute", "Global Mic Mute"),
    ("play_pause", "Play / Pause"),
    ("next_track", "Next Track"),
    ("exit_layer", "Exit HUD"),
];

const POSITIONS: &[(&str, &str, &str)] = &[
    ("top-left", "↖ Top-Left", "Top-Left"),
    ("top-center", "↑ Top-Center", "Top-Center"),
    ("top-right", "↗ Top-Right", "Top-Right"),
    ("bottom-left", "↙ Bottom-Left", "Bottom-Left"),
    ("bottom-center", "↓ Bottom-Center", "Bottom-Center"),
    ("bottom-right", "↘ Bottom-Right", "Bottom-Right"),
];

pub struct SettingsWindow {
    hwnd: HWND,
    config: Arc<Mutex<Config>>,
    recording_action: Option<String>,
}

static mut SETTINGS_INSTANCE: Option<*mut SettingsWindow> = None;

impl SettingsWindow {
    pub fn new(config: Arc<Mutex<Config>>) -> Box<Self> {
        let mut settings = Box::new(Self {
            hwnd: HWND(std::ptr::null_mut()),
            config,
            recording_action: None,
        });

        settings.create_window();
        unsafe {
            SETTINGS_INSTANCE = Some(settings.as_mut() as *mut SettingsWindow);
        }
        settings
    }

    fn create_window(&mut self) {
        unsafe {
            let hinst: HINSTANCE = GetModuleHandleW(None).unwrap_or_default().into();
            let class_name = w!("OpenVolumeSettingsClass");
            let wnd_class = WNDCLASSEXW {
                cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
                style: CS_HREDRAW | CS_VREDRAW,
                lpfnWndProc: Some(settings_wnd_proc),
                hInstance: hinst,
                lpszClassName: PCWSTR(class_name.as_ptr()),
                hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or(HCURSOR(std::ptr::null_mut())),
                hbrBackground: HBRUSH(std::ptr::null_mut()),
                ..Default::default()
            };

            RegisterClassExW(&wnd_class);

            let screen_w = GetSystemMetrics(SM_CXSCREEN);
            let screen_h = GetSystemMetrics(SM_CYSCREEN);
            let win_w = 640;
            let win_h = 760;
            let x = (screen_w - win_w) / 2;
            let y = (screen_h - win_h) / 2;

            let hwnd = CreateWindowExW(
                WINDOW_EX_STYLE(0),
                PCWSTR(class_name.as_ptr()),
                w!("Open-Volume Settings & Customization"),
                WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                x,
                y,
                win_w,
                win_h,
                None,
                None,
                hinst,
                None,
            );

            if let Ok(h) = hwnd {
                self.hwnd = h;
            }
        }
    }

    pub fn show(&self) {
        unsafe {
            let _ = ShowWindow(self.hwnd, SW_SHOWNORMAL);
            let _ = SetForegroundWindow(self.hwnd);
            let _ = InvalidateRect(self.hwnd, None, true);
        }
    }

    pub fn handle_key_down(&mut self, vk: u32) -> bool {
        if self.recording_action.is_none() {
            return false;
        }

        // Cancel on Escape if no modifiers are held
        if vk == VK_ESCAPE.0 as u32 {
            self.recording_action = None;
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, true);
            }
            return true;
        }

        // Ignore standalone modifier presses (wait for the actual key)
        if vk == VK_CONTROL.0 as u32
            || vk == VK_LCONTROL.0 as u32
            || vk == VK_RCONTROL.0 as u32
            || vk == VK_MENU.0 as u32
            || vk == VK_LMENU.0 as u32
            || vk == VK_RMENU.0 as u32
            || vk == VK_SHIFT.0 as u32
            || vk == VK_LSHIFT.0 as u32
            || vk == VK_RSHIFT.0 as u32
            || vk == VK_LWIN.0 as u32
            || vk == VK_RWIN.0 as u32
        {
            return true;
        }

        let ctrl = unsafe { (GetKeyState(VK_CONTROL.0 as i32) as u16 & 0x8000) != 0 };
        let alt = unsafe { (GetKeyState(VK_MENU.0 as i32) as u16 & 0x8000) != 0 };
        let shift = unsafe { (GetKeyState(VK_SHIFT.0 as i32) as u16 & 0x8000) != 0 };
        let win = unsafe {
            ((GetKeyState(VK_LWIN.0 as i32) as u16 & 0x8000) != 0)
                || ((GetKeyState(VK_RWIN.0 as i32) as u16 & 0x8000) != 0)
        };

        let display = format_binding_display(ctrl, alt, shift, win, vk);

        if let Some(act) = self.recording_action.take() {
            let mut cfg = self.config.lock().unwrap();
            cfg.custom_bindings.insert(
                act,
                BindingConfig {
                    vk,
                    ctrl,
                    alt,
                    shift,
                    win,
                    display,
                },
            );
            cfg.save();
            crate::hook::KeyboardHook::update_config(cfg.clone());
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, true);
            }
        }

        true
    }

    fn handle_click(&mut self, x: i32, y: i32) {
        let mut rect = RECT::default();
        unsafe {
            GetClientRect(self.hwnd, &mut rect);
        }
        let width = rect.right - rect.left;

        // 1. GitHub button (x: width - 24 - 120..width - 24, y: 16..46)
        let gh_x = width - 24 - 120;
        if x >= gh_x && x <= gh_x + 120 && (16..=46).contains(&y) {
            unsafe {
                ShellExecuteW(
                    None,
                    w!("open"),
                    w!("https://github.com/shamsghani/open-volume"),
                    None,
                    None,
                    SW_SHOWNORMAL,
                );
            }
            return;
        }

        let themes = list_themes();
        let mut cfg = self.config.lock().unwrap();

        // 2. Theme grid clicks (y: 92..168)
        let theme_w = (width - 48 - 3 * 8) / 4;
        let theme_h = 32;
        for (idx, t) in themes.iter().enumerate() {
            let r = (idx / 4) as i32;
            let c = (idx % 4) as i32;
            let btn_x = 24 + c * (theme_w + 8);
            let btn_y = 92 + r * (theme_h + 6);
            if x >= btn_x && x <= btn_x + theme_w && y >= btn_y && y <= btn_y + theme_h {
                cfg.apply_theme(&t.id);
                cfg.save();
                drop(cfg);
                crate::overlay::refresh_overlay_position();
                unsafe {
                    let _ = InvalidateRect(self.hwnd, None, true);
                }
                return;
            }
        }

        // 3. HUD Position Screen Rectangle (y: 206..302, 6 options)
        let frame_x = 24;
        let frame_y = 206;
        let frame_w = 340;
        let cell_w = (frame_w - 16 - 2 * 6) / 3;
        let cell_h = 36;

        for (idx, (pos_id, _, _)) in POSITIONS.iter().enumerate() {
            let row = (idx / 3) as i32;
            let col = (idx % 3) as i32;
            let cx = frame_x + 8 + col * (cell_w + 6);
            let cy = frame_y + 8 + row * (cell_h + 6);

            if x >= cx && x <= cx + cell_w && y >= cy && y <= cy + cell_h {
                cfg.appearance.position = pos_id.to_string();
                cfg.save();
                drop(cfg);
                crate::overlay::refresh_overlay_position();
                unsafe {
                    let _ = InvalidateRect(self.hwnd, None, true);
                }
                return;
            }
        }

        // 4. Reset Defaults Button (x: width - 24 - 130..width - 24, y: 318..346)
        let reset_x = width - 24 - 130;
        if x >= reset_x && x <= reset_x + 130 && (318..=346).contains(&y) {
            cfg.custom_bindings = Config::default().custom_bindings;
            cfg.save();
            crate::hook::KeyboardHook::update_config(cfg.clone());
            self.recording_action = None;
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, true);
            }
            return;
        }

        // 5. Keybinding rows (y: 352..500)
        let col_w = (width - 48 - 18) / 2;
        let btn_w = 110;
        let btn_h = 24;

        for (idx, (act_key, _)) in BINDING_ACTIONS.iter().enumerate() {
            let col_idx = (idx / 5) as i32;
            let row_idx = (idx % 5) as i32;
            let col_x = if col_idx == 0 { 24 } else { 24 + col_w + 18 };
            let row_y = 352 + row_idx * 28;
            let bx = col_x + col_w - btn_w;
            let by = row_y - 2;

            if x >= bx && x <= bx + btn_w && y >= by && y <= by + btn_h {
                self.recording_action = Some(act_key.to_string());
                unsafe {
                    let _ = InvalidateRect(self.hwnd, None, true);
                }
                return;
            }
        }

        // If clicked outside while recording, cancel recording
        if self.recording_action.is_some() {
            self.recording_action = None;
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, true);
            }
        }

        // 6. Option checkboxes (y: 554..660)
        if (554..=660).contains(&y) {
            if (554..=576).contains(&y) {
                cfg.behavior.follow_focus = !cfg.behavior.follow_focus;
            } else if (580..=602).contains(&y) {
                cfg.volume.perceptual_curve = !cfg.volume.perceptual_curve;
            } else if (606..=628).contains(&y) {
                cfg.behavior.numpad_media_keys = !cfg.behavior.numpad_media_keys;
            } else if (632..=656).contains(&y) {
                let cur = is_startup_enabled();
                let _ = set_startup_enabled(!cur);
                cfg.behavior.start_on_boot = !cur;
            }
            cfg.save();
            crate::hook::KeyboardHook::update_config(cfg.clone());
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, true);
            }
        }
    }

    fn paint(&self, hdc: HDC) {
        unsafe {
            let mut rect = RECT::default();
            GetClientRect(self.hwnd, &mut rect);
            let width = rect.right - rect.left;
            let height = rect.bottom - rect.top;

            // Double-buffer via memory DC for flicker-free rendering
            let mem_dc = CreateCompatibleDC(hdc);
            let mem_bm = CreateCompatibleBitmap(hdc, width, height);
            let old_bm = SelectObject(mem_dc, mem_bm);

            let cfg = self.config.lock().unwrap().clone();
            let app_cfg = &cfg.appearance;

            // Dynamic theme colors applied everywhere!
            let bg_col = hex_to_colorref(&app_cfg.bg_color);
            let card_col = hex_to_colorref(&app_cfg.card_bg);
            let sel_col = hex_to_colorref(&app_cfg.selected_bg);
            let accent_col = hex_to_colorref(&app_cfg.accent_color);
            let text_prim = hex_to_colorref(&app_cfg.text_primary);
            let text_sec = hex_to_colorref(&app_cfg.text_secondary);
            let border_col = hex_to_colorref(&app_cfg.border_color);

            // 1. Window Background
            let bg_brush = CreateSolidBrush(COLORREF(bg_col));
            FillRect(mem_dc, &rect, bg_brush);
            DeleteObject(bg_brush);

            SetBkMode(mem_dc, TRANSPARENT);

            let font_h1 = create_font("Segoe UI", 17, true);
            let font_h2 = create_font("Segoe UI", 12, true);
            let font_body = create_font("Segoe UI", 10, false);
            let font_bold = create_font("Segoe UI", 10, true);
            let font_small = create_font("Segoe UI", 9, false);

            // Header Section
            SelectObject(mem_dc, font_h1);
            SetTextColor(mem_dc, COLORREF(text_prim));
            draw_text(mem_dc, "Open Volume — Settings & Customization", 24, 16, width - 160, 26);

            SelectObject(mem_dc, font_body);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(mem_dc, "Native Win32 audio mixer, HUD overlay, and macropad layer.", 24, 44, width - 160, 18);

            // GitHub Button (Header right)
            let gh_x = width - 24 - 120;
            let gh_brush = CreateSolidBrush(COLORREF(card_col));
            let gh_pen = CreatePen(PS_SOLID, 1, COLORREF(accent_col));
            SelectObject(mem_dc, gh_brush);
            SelectObject(mem_dc, gh_pen);
            RoundRect(mem_dc, gh_x, 16, gh_x + 120, 46, 6, 6);
            DeleteObject(gh_brush);
            DeleteObject(gh_pen);

            SelectObject(mem_dc, font_bold);
            SetTextColor(mem_dc, COLORREF(accent_col));
            draw_text(mem_dc, "⭐ View GitHub", gh_x + 16, 23, 100, 18);

            // Section 1: Themes
            SelectObject(mem_dc, font_h2);
            SetTextColor(mem_dc, COLORREF(accent_col));
            draw_text(mem_dc, "🎨 THEME PALETTES", 24, 70, 200, 18);

            let cur_theme = &app_cfg.theme;
            let themes = list_themes();
            let theme_w = (width - 48 - 3 * 8) / 4;
            let theme_h = 32;

            for (idx, t) in themes.iter().enumerate() {
                let r = (idx / 4) as i32;
                let c = (idx % 4) as i32;
                let btn_x = 24 + c * (theme_w + 8);
                let btn_y = 92 + r * (theme_h + 6);
                let is_sel = t.id.eq_ignore_ascii_case(cur_theme);

                let btn_bg = if is_sel { sel_col } else { card_col };
                let b_col = if is_sel { accent_col } else { border_col };

                let brush = CreateSolidBrush(COLORREF(btn_bg));
                let pen = CreatePen(PS_SOLID, if is_sel { 2 } else { 1 }, COLORREF(b_col));
                SelectObject(mem_dc, brush);
                SelectObject(mem_dc, pen);
                RoundRect(mem_dc, btn_x, btn_y, btn_x + theme_w, btn_y + theme_h, 6, 6);
                DeleteObject(brush);
                DeleteObject(pen);

                SelectObject(mem_dc, font_bold);
                SetTextColor(mem_dc, if is_sel { COLORREF(accent_col) } else { COLORREF(text_prim) });
                let label = format!("{} {}", t.emoji, t.name);
                draw_text(mem_dc, &label, btn_x + 8, btn_y + 8, theme_w - 16, 18);
            }

            // Section 2: HUD Position (Illustrated Monitor Rectangle with all 6 positions)
            SelectObject(mem_dc, font_h2);
            SetTextColor(mem_dc, COLORREF(accent_col));
            draw_text(mem_dc, "📐 HUD SCREEN POSITION", 24, 182, 220, 18);

            let frame_x = 24;
            let frame_y = 206;
            let frame_w = 340;
            let frame_h = 96;

            // Monitor Outer Frame
            let frame_brush = CreateSolidBrush(COLORREF(card_col));
            let frame_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
            SelectObject(mem_dc, frame_brush);
            SelectObject(mem_dc, frame_pen);
            RoundRect(mem_dc, frame_x, frame_y, frame_x + frame_w, frame_y + frame_h, 8, 8);
            DeleteObject(frame_brush);
            DeleteObject(frame_pen);

            let cell_w = (frame_w - 16 - 2 * 6) / 3;
            let cell_h = 36;
            let cur_pos = app_cfg.position.to_lowercase();

            for (idx, (pos_id, icon_label, _)) in POSITIONS.iter().enumerate() {
                let row = (idx / 3) as i32;
                let col = (idx % 3) as i32;
                let cx = frame_x + 8 + col * (cell_w + 6);
                let cy = frame_y + 8 + row * (cell_h + 6);
                let is_sel = pos_id.eq_ignore_ascii_case(&cur_pos);

                let cell_bg = if is_sel { sel_col } else { bg_col };
                let cell_border = if is_sel { accent_col } else { border_col };

                let brush = CreateSolidBrush(COLORREF(cell_bg));
                let pen = CreatePen(PS_SOLID, if is_sel { 2 } else { 1 }, COLORREF(cell_border));
                SelectObject(mem_dc, brush);
                SelectObject(mem_dc, pen);
                RoundRect(mem_dc, cx, cy, cx + cell_w, cy + cell_h, 4, 4);
                DeleteObject(brush);
                DeleteObject(pen);

                SelectObject(mem_dc, font_bold);
                SetTextColor(mem_dc, if is_sel { COLORREF(accent_col) } else { COLORREF(text_sec) });
                draw_text(mem_dc, icon_label, cx + 8, cy + 9, cell_w - 16, 18);
            }

            // Right side of monitor rectangle: Position info & explanation
            let info_x = frame_x + frame_w + 16;
            let info_w = width - info_x - 24;

            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(mem_dc, "Active Dock Anchor:", info_x, frame_y + 8, info_w, 16);

            SelectObject(mem_dc, font_h2);
            SetTextColor(mem_dc, COLORREF(accent_col));
            let active_display_name = POSITIONS
                .iter()
                .find(|(id, _, _)| id.eq_ignore_ascii_case(&cur_pos))
                .map(|(_, _, name)| *name)
                .unwrap_or("Top-Center");
            draw_text(mem_dc, active_display_name, info_x, frame_y + 26, info_w, 20);

            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(
                mem_dc,
                "Click any anchor inside the monitor frame to dock the HUD overlay to that screen edge.",
                info_x,
                frame_y + 50,
                info_w,
                40,
            );

            // Section 3: Custom Shortcuts & Keybindings
            SelectObject(mem_dc, font_h2);
            SetTextColor(mem_dc, COLORREF(accent_col));
            draw_text(mem_dc, "⌨️ CUSTOM KEYBINDINGS & SHORTCUTS", 24, 322, 320, 18);

            // Reset Defaults Button
            let reset_x = width - 24 - 130;
            let r_brush = CreateSolidBrush(COLORREF(card_col));
            let r_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
            SelectObject(mem_dc, r_brush);
            SelectObject(mem_dc, r_pen);
            RoundRect(mem_dc, reset_x, 318, reset_x + 130, 346, 4, 4);
            DeleteObject(r_brush);
            DeleteObject(r_pen);

            SelectObject(mem_dc, font_bold);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(mem_dc, "🔄 Reset Defaults", reset_x + 14, 324, 110, 18);

            // Keybinding Table (2 columns of 5 actions)
            let col_w = (width - 48 - 18) / 2;
            let btn_w = 110;
            let btn_h = 24;

            for (idx, (act_key, act_name)) in BINDING_ACTIONS.iter().enumerate() {
                let col_idx = (idx / 5) as i32;
                let row_idx = (idx % 5) as i32;
                let col_x = if col_idx == 0 { 24 } else { 24 + col_w + 18 };
                let row_y = 352 + row_idx * 28;
                let bx = col_x + col_w - btn_w;
                let by = row_y - 2;

                // Action label
                SelectObject(mem_dc, font_bold);
                SetTextColor(mem_dc, COLORREF(text_prim));
                draw_text(mem_dc, act_name, col_x, row_y + 2, col_w - btn_w - 8, 18);

                // Button
                let is_recording = self.recording_action.as_deref() == Some(*act_key);
                let btn_bg = if is_recording { sel_col } else { card_col };
                let btn_border = if is_recording { accent_col } else { border_col };

                let b_brush = CreateSolidBrush(COLORREF(btn_bg));
                let b_pen = CreatePen(PS_SOLID, if is_recording { 2 } else { 1 }, COLORREF(btn_border));
                SelectObject(mem_dc, b_brush);
                SelectObject(mem_dc, b_pen);
                RoundRect(mem_dc, bx, by, bx + btn_w, by + btn_h, 4, 4);
                DeleteObject(b_brush);
                DeleteObject(b_pen);

                let display_str = if is_recording {
                    "[ Press Key... ]".to_string()
                } else {
                    cfg.custom_bindings
                        .get(*act_key)
                        .map(|b| b.display.clone())
                        .unwrap_or_else(|| "None".to_string())
                };

                SelectObject(mem_dc, font_bold);
                SetTextColor(mem_dc, COLORREF(accent_col));
                draw_text(mem_dc, &display_str, bx + 6, by + 4, btn_w - 12, 18);
            }

            // Hint under keybindings
            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(
                mem_dc,
                "💡 Click any shortcut button, then press your desired key or combination. Press Escape to cancel.",
                24,
                502,
                width - 48,
                16,
            );

            // Section 4: Options & Behavior
            SelectObject(mem_dc, font_h2);
            SetTextColor(mem_dc, COLORREF(accent_col));
            draw_text(mem_dc, "⚙️ OPTIONS & BEHAVIOR", 24, 530, 220, 18);

            let options = [
                (cfg.behavior.follow_focus, "Follow Focus (Auto-select active foreground window on layer activation)"),
                (cfg.volume.perceptual_curve, "Perceptual Logarithmic Volume Curve (Natural acoustic human hearing response)"),
                (cfg.behavior.numpad_media_keys, "Numpad Media Keys (7 = Prev Track, 9 = Next Track, 3 = Play / Pause)"),
                (is_startup_enabled(), "Start automatically on Windows login (High Integrity / No UAC prompt)"),
            ];

            let mut opt_y = 554;
            for (checked, desc) in options {
                let check_char = if checked { "☑" } else { "☐" };
                SelectObject(mem_dc, font_bold);
                SetTextColor(mem_dc, if checked { COLORREF(accent_col) } else { COLORREF(text_sec) });
                draw_text(mem_dc, check_char, 24, opt_y, 20, 18);

                SelectObject(mem_dc, font_body);
                SetTextColor(mem_dc, COLORREF(text_prim));
                draw_text(mem_dc, desc, 48, opt_y, width - 60, 18);
                opt_y += 26;
            }

            // Footer note
            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(mem_dc, "Settings and keybindings are automatically saved to config.json.", 24, height - 30, width - 48, 16);

            // Blit to screen and cleanup
            let _ = BitBlt(hdc, 0, 0, width, height, mem_dc, 0, 0, SRCCOPY);

            SelectObject(mem_dc, old_bm);
            DeleteObject(mem_bm);
            DeleteDC(mem_dc);

            DeleteObject(font_h1);
            DeleteObject(font_h2);
            DeleteObject(font_body);
            DeleteObject(font_bold);
            DeleteObject(font_small);
        }
    }
}

pub fn format_binding_display(ctrl: bool, alt: bool, shift: bool, win: bool, vk: u32) -> String {
    let mut parts = Vec::new();
    if ctrl { parts.push("Ctrl".to_string()); }
    if alt { parts.push("Alt".to_string()); }
    if shift { parts.push("Shift".to_string()); }
    if win { parts.push("Win".to_string()); }

    let key_name = match vk {
        0x08 => "Backspace".to_string(),
        0x09 => "Tab".to_string(),
        0x0D => "Enter".to_string(),
        0x1B => "Escape".to_string(),
        0x20 => "Space".to_string(),
        0x21 => "Page Up".to_string(),
        0x22 => "Page Down".to_string(),
        0x23 => "End".to_string(),
        0x24 => "Home".to_string(),
        0x25 => "Left Arrow".to_string(),
        0x26 => "Up Arrow".to_string(),
        0x27 => "Right Arrow".to_string(),
        0x28 => "Down Arrow".to_string(),
        0x2D => "Insert".to_string(),
        0x2E => "Delete".to_string(),
        0x30..=0x39 => format!("{}", (vk - 0x30) as u8 as char),
        0x41..=0x5A => format!("{}", (vk - 0x41 + b'A' as u32) as u8 as char),
        0x60..=0x69 => format!("Num {}", vk - 0x60),
        0x6A => "Num *".to_string(),
        0x6B => "Num +".to_string(),
        0x6D => "Num -".to_string(),
        0x6E => "Num .".to_string(),
        0x6F => "Num /".to_string(),
        0x70..=0x87 => format!("F{}", vk - 0x6F),
        0x90 => "NumLock".to_string(),
        0x91 => "ScrollLock".to_string(),
        0xBA => ";".to_string(),
        0xBB => "=".to_string(),
        0xBC => ",".to_string(),
        0xBD => "-".to_string(),
        0xBE => ".".to_string(),
        0xBF => "/".to_string(),
        0xC0 => "`".to_string(),
        0xDB => "[".to_string(),
        0xDC => "\\".to_string(),
        0xDD => "]".to_string(),
        0xDE => "'".to_string(),
        _ => format!("Key 0x{:02X}", vk),
    };
    parts.push(key_name);
    parts.join(" + ")
}

unsafe fn create_font(name: &str, size: i32, bold: bool) -> HFONT {
    let hname = HSTRING::from(name);
    CreateFontW(
        -size,
        0,
        0,
        0,
        if bold { FW_BOLD.0 as i32 } else { FW_NORMAL.0 as i32 },
        0,
        0,
        0,
        DEFAULT_CHARSET.0 as u32,
        OUT_DEFAULT_PRECIS.0 as u32,
        CLIP_DEFAULT_PRECIS.0 as u32,
        CLEARTYPE_QUALITY.0 as u32,
        VARIABLE_PITCH.0 as u32,
        PCWSTR(hname.as_ptr()),
    )
}

unsafe fn draw_text(hdc: HDC, text: &str, x: i32, y: i32, w: i32, h: i32) {
    let mut rect = RECT {
        left: x,
        top: y,
        right: x + w,
        bottom: y + h,
    };
    let hstr = HSTRING::from(text);
    let mut wide: Vec<u16> = hstr.as_wide().to_vec();
    DrawTextW(hdc, &mut wide, &mut rect, DT_LEFT | DT_SINGLELINE | DT_NOPREFIX);
}

unsafe extern "system" fn settings_wnd_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_LBUTTONDOWN => {
            let x = (lparam.0 & 0xFFFF) as i32;
            let y = ((lparam.0 >> 16) & 0xFFFF) as i32;
            if let Some(inst_ptr) = SETTINGS_INSTANCE {
                let inst = &mut *inst_ptr;
                inst.handle_click(x, y);
            }
            LRESULT(0)
        }
        WM_KEYDOWN | WM_SYSKEYDOWN => {
            let vk = wparam.0 as u32;
            if let Some(inst_ptr) = SETTINGS_INSTANCE {
                let inst = &mut *inst_ptr;
                if inst.handle_key_down(vk) {
                    return LRESULT(0);
                }
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            if let Some(inst_ptr) = SETTINGS_INSTANCE {
                let inst = &*inst_ptr;
                inst.paint(hdc);
            }
            EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_ERASEBKGND => LRESULT(1),
        WM_CLOSE => {
            let _ = ShowWindow(hwnd, SW_HIDE);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}
