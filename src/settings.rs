use crate::config::{list_themes, Config};
use crate::startup::{is_startup_enabled, set_startup_enabled};
use std::sync::{Arc, Mutex};
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::*;

pub struct SettingsWindow {
    hwnd: HWND,
    config: Arc<Mutex<Config>>,
}

static mut SETTINGS_INSTANCE: Option<*mut SettingsWindow> = None;

impl SettingsWindow {
    pub fn new(config: Arc<Mutex<Config>>) -> Box<Self> {
        let mut settings = Box::new(Self {
            hwnd: HWND(std::ptr::null_mut()),
            config,
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
                hbrBackground: HBRUSH((COLOR_WINDOW.0 + 1) as *mut _),
                ..Default::default()
            };

            RegisterClassExW(&wnd_class);

            let hwnd = CreateWindowExW(
                WINDOW_EX_STYLE(0),
                PCWSTR(class_name.as_ptr()),
                w!("Open-Volume Settings"),
                WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                CW_USEDEFAULT,
                CW_USEDEFAULT,
                580,
                640,
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

    fn handle_click(&self, x: i32, y: i32) {
        let themes = list_themes();
        let mut cfg = self.config.lock().unwrap();

        // 1. Theme grid clicks (y: 110..220)
        if (110..=220).contains(&y) {
            for (idx, t) in themes.iter().enumerate() {
                let r = idx / 4;
                let c = idx % 4;
                let btn_x = 24 + (c as i32) * 130;
                let btn_y = 110 + (r as i32) * 48;
                if x >= btn_x && x <= btn_x + 120 && y >= btn_y && y <= btn_y + 38 {
                    cfg.apply_theme(&t.id);
                    cfg.save();
                    unsafe { let _ = InvalidateRect(self.hwnd, None, true); }
                    return;
                }
            }
        }

        // 2. Position clicks (y: 280..320)
        let positions = ["top-center", "bottom-right", "top-right", "bottom-center"];
        if (280..=320).contains(&y) {
            for (idx, pos) in positions.iter().enumerate() {
                let btn_x = 24 + (idx as i32) * 130;
                if x >= btn_x && x <= btn_x + 120 {
                    cfg.appearance.position = pos.to_string();
                    cfg.save();
                    unsafe { let _ = InvalidateRect(self.hwnd, None, true); }
                    return;
                }
            }
        }

        // 3. Option checkboxes (y: 360..500)
        if (360..=500).contains(&y) {
            if (360..=385).contains(&y) {
                cfg.behavior.follow_focus = !cfg.behavior.follow_focus;
            } else if (395..=420).contains(&y) {
                cfg.volume.perceptual_curve = !cfg.volume.perceptual_curve;
            } else if (430..=455).contains(&y) {
                cfg.behavior.numpad_media_keys = !cfg.behavior.numpad_media_keys;
            } else if (465..=490).contains(&y) {
                let cur = is_startup_enabled();
                let _ = set_startup_enabled(!cur);
                cfg.behavior.start_on_boot = !cur;
            }
            cfg.save();
            unsafe { let _ = InvalidateRect(self.hwnd, None, true); }
        }
    }

    fn paint(&self, hdc: HDC) {
        unsafe {
            let mut rect = RECT::default();
            GetClientRect(self.hwnd, &mut rect);
            let width = rect.right - rect.left;
            let height = rect.bottom - rect.top;

            let cfg = self.config.lock().unwrap().clone();
            let themes = list_themes();

            let bg_brush = CreateSolidBrush(COLORREF(0x00181312));
            FillRect(hdc, &rect, bg_brush);
            DeleteObject(bg_brush);

            SetBkMode(hdc, TRANSPARENT);

            let font_h1 = create_font("Segoe UI", 18, true);
            let font_h2 = create_font("Segoe UI", 13, true);
            let font_body = create_font("Segoe UI", 11, false);
            let font_bold = create_font("Segoe UI", 11, true);

            // Title Header
            SelectObject(hdc, font_h1);
            SetTextColor(hdc, COLORREF(0x00FFFFFF));
            draw_text(hdc, "Open Volume — Settings & Customization", 24, 20, width - 48, 28);

            SelectObject(hdc, font_body);
            SetTextColor(hdc, COLORREF(0x00A6908E));
            draw_text(hdc, "High-performance native audio mixer, HUD overlay, and macropad layer.", 24, 52, width - 48, 20);

            // 1. Themes Section
            SelectObject(hdc, font_h2);
            SetTextColor(hdc, COLORREF(0x0000E5A3));
            draw_text(hdc, "Theme Palettes", 24, 85, 200, 20);

            let cur_theme = &cfg.appearance.theme;
            for (idx, t) in themes.iter().enumerate() {
                let r = idx / 4;
                let c = idx % 4;
                let btn_x = 24 + (c as i32) * 130;
                let btn_y = 110 + (r as i32) * 48;

                let is_sel = t.id.eq_ignore_ascii_case(cur_theme);
                let btn_bg = if is_sel { 0x00382824 } else { 0x00241B1A };
                let border_col = if is_sel { 0x0000E5A3 } else { 0x003C2D2A };

                let brush = CreateSolidBrush(COLORREF(btn_bg));
                let pen = CreatePen(PS_SOLID, if is_sel { 2 } else { 1 }, COLORREF(border_col));
                SelectObject(hdc, brush);
                SelectObject(hdc, pen);
                RoundRect(hdc, btn_x, btn_y, btn_x + 120, btn_y + 38, 8, 8);
                DeleteObject(brush);
                DeleteObject(pen);

                SelectObject(hdc, font_bold);
                SetTextColor(hdc, if is_sel { COLORREF(0x0000E5A3) } else { COLORREF(0x00FFFFFF) });
                let label = format!("{} {}", t.emoji, t.name);
                draw_text(hdc, &label, btn_x + 8, btn_y + 10, 104, 18);
            }

            // 2. Position Section
            SelectObject(hdc, font_h2);
            SetTextColor(hdc, COLORREF(0x0000E5A3));
            draw_text(hdc, "HUD Position", 24, 255, 200, 20);

            let cur_pos = &cfg.appearance.position;
            let positions = [
                ("top-center", "Top-Center"),
                ("bottom-right", "Bottom-Right"),
                ("top-right", "Top-Right"),
                ("bottom-center", "Bottom-Center"),
            ];

            for (idx, (pos_id, label)) in positions.iter().enumerate() {
                let btn_x = 24 + (idx as i32) * 130;
                let btn_y = 280;
                let is_sel = pos_id.eq_ignore_ascii_case(cur_pos);

                let btn_bg = if is_sel { 0x00382824 } else { 0x00241B1A };
                let border_col = if is_sel { 0x0000E5A3 } else { 0x003C2D2A };

                let brush = CreateSolidBrush(COLORREF(btn_bg));
                let pen = CreatePen(PS_SOLID, if is_sel { 2 } else { 1 }, COLORREF(border_col));
                SelectObject(hdc, brush);
                SelectObject(hdc, pen);
                RoundRect(hdc, btn_x, btn_y, btn_x + 120, btn_y + 36, 8, 8);
                DeleteObject(brush);
                DeleteObject(pen);

                SelectObject(hdc, font_bold);
                SetTextColor(hdc, if is_sel { COLORREF(0x0000E5A3) } else { COLORREF(0x00FFFFFF) });
                draw_text(hdc, label, btn_x + 10, btn_y + 9, 100, 18);
            }

            // 3. Behavior & Options Section
            SelectObject(hdc, font_h2);
            SetTextColor(hdc, COLORREF(0x0000E5A3));
            draw_text(hdc, "Options & Behavior", 24, 335, 200, 20);

            SelectObject(hdc, font_body);
            SetTextColor(hdc, COLORREF(0x00FFFFFF));

            let options = [
                (cfg.behavior.follow_focus, "Follow Focus (Auto-select active foreground window on layer activation)"),
                (cfg.volume.perceptual_curve, "Perceptual Logarithmic Volume Curve (Natural human hearing response)"),
                (cfg.behavior.numpad_media_keys, "Numpad Media Keys (7=Prev, 9=Next, 3=Play/Pause)"),
                (is_startup_enabled(), "Start automatically on Windows login (High Integrity / No UAC)"),
            ];

            let mut opt_y = 365;
            for (checked, desc) in options {
                let check_char = if checked { "☑" } else { "☐" };
                SetTextColor(hdc, if checked { COLORREF(0x0000E5A3) } else { COLORREF(0x00A6908E) });
                draw_text(hdc, check_char, 24, opt_y, 20, 18);

                SetTextColor(hdc, COLORREF(0x00FFFFFF));
                draw_text(hdc, desc, 48, opt_y, width - 60, 18);
                opt_y += 35;
            }

            // Footer note
            SelectObject(hdc, font_body);
            SetTextColor(hdc, COLORREF(0x008E90A6));
            draw_text(hdc, "Settings are saved automatically to config.json.", 24, height - 35, width - 48, 18);

            DeleteObject(font_h1);
            DeleteObject(font_h2);
            DeleteObject(font_body);
            DeleteObject(font_bold);
        }
    }
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
                let inst = &*inst_ptr;
                inst.handle_click(x, y);
            }
            LRESULT(0)
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
        WM_CLOSE => {
            let _ = ShowWindow(hwnd, SW_HIDE);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}
