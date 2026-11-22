use crate::audio::AudioMixer;
use crate::config::{hex_to_colorref, Config};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Dwm::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::UI::WindowsAndMessaging::*;

use windows::Win32::System::LibraryLoader::GetModuleHandleW;

const TIMER_ANIM_ID: usize = 1;
const TIMER_VU_ID: usize = 2;
const TIMER_AUTOHIDE_ID: usize = 3;

pub struct OverlayWindow {
    hwnd: HWND,
    main_hwnd: HWND,
    config: Arc<Mutex<Config>>,
    mixer: Arc<Mutex<AudioMixer>>,
    visible: bool,
    anim_in_progress: bool,
    anim_fade_out: bool,
    anim_start_time: Instant,
    target_x: i32,
    target_y: i32,
    target_h: i32,
    slide_dx: i32,
    slide_dy: i32,
    last_activity: Instant,
    toast_text: Option<String>,
    toast_icon: String,
    toast_time: Instant,
    // VU meter ballistic smoothing
    smoothed_master_peak: f32,
    peak_hold: f32,
    peak_hold_time: Instant,
    smoothed_app_peaks: Vec<f32>,
}

static mut OVERLAY_INSTANCE: Option<*mut OverlayWindow> = None;

impl OverlayWindow {
    pub fn new(main_hwnd: HWND, config: Arc<Mutex<Config>>, mixer: Arc<Mutex<AudioMixer>>) -> Box<Self> {
        let mut overlay = Box::new(Self {
            hwnd: HWND(std::ptr::null_mut()),
            main_hwnd,
            config,
            mixer,
            visible: false,
            anim_in_progress: false,
            anim_fade_out: false,
            anim_start_time: Instant::now(),
            target_x: 0,
            target_y: 0,
            target_h: 380,
            slide_dx: 0,
            slide_dy: 0,
            last_activity: Instant::now(),
            toast_text: None,
            toast_icon: String::new(),
            toast_time: Instant::now(),
            smoothed_master_peak: 0.0,
            peak_hold: 0.0,
            peak_hold_time: Instant::now(),
            smoothed_app_peaks: Vec::new(),
        });

        overlay.create_window();
        unsafe {
            OVERLAY_INSTANCE = Some(overlay.as_mut() as *mut OverlayWindow);
        }
        overlay
    }

    fn create_window(&mut self) {
        unsafe {
            let hinst: HINSTANCE = GetModuleHandleW(None).unwrap_or_default().into();
            let class_name = w!("OpenVolumeOverlayClass");
            let wnd_class = WNDCLASSEXW {
                cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
                style: CS_HREDRAW | CS_VREDRAW,
                lpfnWndProc: Some(overlay_wnd_proc),
                hInstance: hinst,
                lpszClassName: PCWSTR(class_name.as_ptr()),
                hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or(HCURSOR(std::ptr::null_mut())),
                ..Default::default()
            };

            RegisterClassExW(&wnd_class);

            let hwnd = CreateWindowExW(
                WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                PCWSTR(class_name.as_ptr()),
                w!("OpenVolume Overlay"),
                WS_POPUP,
                0,
                0,
                360,
                380,
                None,
                None,
                hinst,
                None,
            );

            if let Ok(h) = hwnd {
                self.hwnd = h;
                let _ = SetLayeredWindowAttributes(h, COLORREF(0), 0, LWA_ALPHA);
                self.reassert_topmost();
            }
        }
    }

    pub fn hwnd(&self) -> HWND {
        self.hwnd
    }

    pub fn reassert_topmost(&self) {
        unsafe {
            let _ = SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            );
        }
    }

    pub fn apply_rounded_corners(&self, width: i32, height: i32) {
        unsafe {
            let rgn = CreateRoundRectRgn(0, 0, width + 1, height + 1, 20, 20);
            if !rgn.0.is_null() {
                SetWindowRgn(self.hwnd, rgn, true);
            }

            let preference: u32 = 2; // DWMWCP_ROUND
            let _ = DwmSetWindowAttribute(
                self.hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                &preference as *const _ as *const _,
                std::mem::size_of::<u32>() as u32,
            );
        }
    }

    pub fn calculate_position(&mut self, height: i32) -> (i32, i32, i32, i32) {
        let (work_w, work_h, work_left, work_top) = get_primary_work_area();
        let cfg = self.config.lock().unwrap();
        let pos = cfg.appearance.position.to_lowercase();
        let width = cfg.appearance.width;
        let margin_x = cfg.appearance.margin_x;
        let margin_y = cfg.appearance.margin_y;

        let (x, slide_dx) = if pos.contains("left") {
            (work_left + margin_x, -24)
        } else if pos.contains("right") {
            (work_left + work_w - width - margin_x, 24)
        } else {
            (work_left + (work_w - width) / 2, 0)
        };

        let (y, mut slide_dy) = if pos.contains("top") {
            (work_top + margin_y, -24)
        } else if pos.contains("bottom") {
            (work_top + work_h - height - margin_y, 24)
        } else {
            (work_top + (work_h - height) / 2, 0)
        };

        if slide_dx == 0 && slide_dy == 0 {
            slide_dy = 20;
        }

        (x, y, slide_dx, slide_dy)
    }

    pub fn show(&mut self) {
        self.visible = true;
        self.last_activity = Instant::now();

        // Calculate height
        let (list_len, has_toast) = {
            let mixer = self.mixer.lock().unwrap();
            let toast_active = self.toast_text.is_some() && self.toast_time.elapsed() < Duration::from_secs(3);
            (mixer.get_apps().len(), toast_active)
        };

        let max_visible = self.config.lock().unwrap().appearance.max_visible_apps;
        let list_count = list_len.min(max_visible);
        let extra_h = if has_toast { 32 } else { 0 };
        let height = 56 + 98 + (list_count as i32 * 32) + 40 + extra_h;

        let (x, y, dx, dy) = self.calculate_position(height);
        self.target_x = x;
        self.target_y = y;
        self.target_h = height;
        self.slide_dx = dx;
        self.slide_dy = dy;

        let anim_enabled = self.config.lock().unwrap().appearance.animation_enabled;
        let width = self.config.lock().unwrap().appearance.width;

        unsafe {
            if !anim_enabled {
                self.anim_in_progress = false;
                self.anim_fade_out = false;
                let _ = SetWindowPos(
                    self.hwnd,
                    HWND_TOPMOST,
                    x,
                    y,
                    width,
                    height,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW,
                );
                let _ = ShowWindow(self.hwnd, SW_SHOWNOACTIVATE);
                self.apply_rounded_corners(width, height);
                let _ = SetLayeredWindowAttributes(self.hwnd, COLORREF(0), 255, LWA_ALPHA);
                let _ = InvalidateRect(self.hwnd, None, false);
            } else {
                self.anim_in_progress = true;
                self.anim_fade_out = false;
                self.anim_start_time = Instant::now();
                let start_x = x + dx;
                let start_y = y + dy;
                let _ = SetWindowPos(
                    self.hwnd,
                    HWND_TOPMOST,
                    start_x,
                    start_y,
                    width,
                    height,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW,
                );
                let _ = ShowWindow(self.hwnd, SW_SHOWNOACTIVATE);
                self.apply_rounded_corners(width, height);
                let _ = SetLayeredWindowAttributes(self.hwnd, COLORREF(0), 12, LWA_ALPHA);
                let _ = SetTimer(self.hwnd, TIMER_ANIM_ID, 16, None);
            }

            let _ = SetTimer(self.hwnd, TIMER_VU_ID, 33, None);
            let _ = SetTimer(self.hwnd, TIMER_AUTOHIDE_ID, 250, None);
        }
        self.reassert_topmost();
    }

    pub fn hide(&mut self) {
        if !self.visible && !self.anim_in_progress {
            return;
        }

        let anim_enabled = self.config.lock().unwrap().appearance.animation_enabled;
        if anim_enabled && self.visible && !self.anim_fade_out {
            self.anim_in_progress = true;
            self.anim_fade_out = true;
            self.anim_start_time = Instant::now();
            unsafe {
                let _ = KillTimer(self.hwnd, TIMER_VU_ID);
                let _ = KillTimer(self.hwnd, TIMER_AUTOHIDE_ID);
                let _ = SetTimer(self.hwnd, TIMER_ANIM_ID, 16, None);
            }
        } else if !anim_enabled {
            self.hide_instant();
        }
    }

    pub fn hide_instant(&mut self) {
        self.visible = false;
        self.anim_in_progress = false;
        self.anim_fade_out = false;
        unsafe {
            let _ = KillTimer(self.hwnd, TIMER_ANIM_ID);
            let _ = KillTimer(self.hwnd, TIMER_VU_ID);
            let _ = KillTimer(self.hwnd, TIMER_AUTOHIDE_ID);
            let _ = ShowWindow(self.hwnd, SW_HIDE);
        }
    }

    pub fn show_toast(&mut self, text: &str, icon: &str) {
        self.toast_text = Some(text.to_string());
        self.toast_icon = icon.to_string();
        self.toast_time = Instant::now();
        self.last_activity = Instant::now();
        if self.visible {
            self.recalc_height_and_reposition();
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, false);
            }
        } else {
            self.show();
        }
    }

    pub fn recalc_height_and_reposition(&mut self) {
        let (list_len, has_toast) = {
            let mixer = self.mixer.lock().unwrap();
            let toast_active = self.toast_text.is_some() && self.toast_time.elapsed() < Duration::from_millis(2200);
            (mixer.get_apps().len(), toast_active)
        };

        let max_visible = self.config.lock().unwrap().appearance.max_visible_apps;
        let list_count = list_len.min(max_visible);
        let extra_h = if has_toast { 34 } else { 0 };
        let height = 56 + 98 + (list_count as i32 * 32) + 40 + extra_h;
        let width = self.config.lock().unwrap().appearance.width;

        let (x, y, _, _) = self.calculate_position(height);
        self.target_x = x;
        self.target_y = y;
        self.target_h = height;

        unsafe {
            let _ = SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                x,
                y,
                width,
                height,
                SWP_NOACTIVATE | SWP_NOZORDER,
            );
            self.apply_rounded_corners(width, height);
        }
    }

    pub fn update_display(&mut self) {
        self.last_activity = Instant::now();
        if self.visible {
            self.reassert_topmost();
            unsafe {
                let _ = InvalidateRect(self.hwnd, None, false);
            }
        }
    }

    fn step_animation(&mut self) {
        if !self.anim_in_progress {
            unsafe { let _ = KillTimer(self.hwnd, TIMER_ANIM_ID); }
            return;
        }

        let width = self.config.lock().unwrap().appearance.width;

        if !self.anim_fade_out {
            // Slide in & fade in
            let duration_ms = self.config.lock().unwrap().appearance.animation_duration_ms.max(50);
            let elapsed = self.anim_start_time.elapsed().as_millis() as f32;
            let t = (elapsed / duration_ms as f32).clamp(0.0, 1.0);
            let ease = 1.0 - (1.0 - t).powi(3);

            let cur_x = (self.target_x as f32 + self.slide_dx as f32 * (1.0 - ease)) as i32;
            let cur_y = (self.target_y as f32 + self.slide_dy as f32 * (1.0 - ease)) as i32;
            let cur_alpha = ((12.0 + 243.0 * ease).round() as u8).max(12);

            unsafe {
                let _ = SetWindowPos(
                    self.hwnd,
                    HWND_TOPMOST,
                    cur_x,
                    cur_y,
                    width,
                    self.target_h,
                    SWP_NOACTIVATE | SWP_NOZORDER,
                );
                let _ = SetLayeredWindowAttributes(self.hwnd, COLORREF(0), cur_alpha, LWA_ALPHA);
                let _ = InvalidateRect(self.hwnd, None, false);

                if t >= 1.0 {
                    self.anim_in_progress = false;
                    let _ = KillTimer(self.hwnd, TIMER_ANIM_ID);
                    let _ = SetLayeredWindowAttributes(self.hwnd, COLORREF(0), 255, LWA_ALPHA);
                    let _ = SetWindowPos(
                        self.hwnd,
                        HWND_TOPMOST,
                        self.target_x,
                        self.target_y,
                        width,
                        self.target_h,
                        SWP_NOACTIVATE | SWP_NOZORDER,
                    );
                }
            }
            self.reassert_topmost();
        } else {
            // Slide out & fade out
            let duration_ms = ((self.config.lock().unwrap().appearance.animation_duration_ms.max(50) as f32) * 0.7)
                .clamp(70.0, 150.0) as u32;
            let elapsed = self.anim_start_time.elapsed().as_millis() as f32;
            let t = (elapsed / duration_ms as f32).clamp(0.0, 1.0);
            let ease = t.powi(3);

            let cur_x = (self.target_x as f32 + self.slide_dx as f32 * ease) as i32;
            let cur_y = (self.target_y as f32 + self.slide_dy as f32 * ease) as i32;
            let cur_alpha = (255.0 * (1.0 - ease)).round() as u8;

            unsafe {
                if t >= 1.0 {
                    self.hide_instant();
                } else {
                    let _ = SetWindowPos(
                        self.hwnd,
                        HWND_TOPMOST,
                        cur_x,
                        cur_y,
                        width,
                        self.target_h,
                        SWP_NOACTIVATE | SWP_NOZORDER,
                    );
                    let _ = SetLayeredWindowAttributes(self.hwnd, COLORREF(0), cur_alpha, LWA_ALPHA);
                    let _ = InvalidateRect(self.hwnd, None, false);
                }
            }
        }
    }

    fn poll_vu_meter(&mut self) {
        if !self.visible {
            return;
        }

        let (master_pk, app_peaks) = {
            let mixer = self.mixer.lock().unwrap();
            mixer.get_peak_levels()
        };

        // Ballistic instant attack, exponential decay
        if master_pk >= self.smoothed_master_peak {
            self.smoothed_master_peak = master_pk;
        } else {
            self.smoothed_master_peak = self.smoothed_master_peak * 0.82 + master_pk * 0.18;
        }

        // Peak hold needle
        let now = Instant::now();
        if master_pk >= self.peak_hold {
            self.peak_hold = master_pk;
            self.peak_hold_time = now;
        } else if now.duration_since(self.peak_hold_time) > Duration::from_millis(600) {
            self.peak_hold = (self.peak_hold - 0.03).max(master_pk);
        }

        // App peaks
        if self.smoothed_app_peaks.len() != app_peaks.len() {
            self.smoothed_app_peaks = vec![0.0; app_peaks.len()];
        }
        for (i, &pk) in app_peaks.iter().enumerate() {
            if pk >= self.smoothed_app_peaks[i] {
                self.smoothed_app_peaks[i] = pk;
            } else {
                self.smoothed_app_peaks[i] = self.smoothed_app_peaks[i] * 0.85 + pk * 0.15;
            }
        }

        self.reassert_topmost();
        unsafe {
            let _ = InvalidateRect(self.hwnd, None, false);
        }
    }

    fn check_autohide(&mut self) {
        if !self.visible || self.anim_fade_out {
            return;
        }
        let is_layer_active = crate::hook::KeyboardHook::is_layer_active();
        let timeout_secs = if is_layer_active {
            self.config.lock().unwrap().behavior.auto_hide_seconds
        } else {
            2
        };
        if timeout_secs > 0 && self.last_activity.elapsed() >= Duration::from_secs(timeout_secs) {
            crate::log_event("Overlay autohide timeout elapsed. Hiding overlay and deactivating layer if active.");
            if is_layer_active {
                crate::hook::KeyboardHook::set_layer_active(false);
                if !self.main_hwnd.0.is_null() {
                    unsafe {
                        let _ = windows::Win32::UI::WindowsAndMessaging::PostMessageW(
                            self.main_hwnd,
                            crate::hook::WM_APP_ACTION,
                            windows::Win32::Foundation::WPARAM(2), // AppAction::LayerExit
                            windows::Win32::Foundation::LPARAM(0),
                        );
                    }
                }
            }
            self.hide();
        }
    }

    fn paint(&self, hdc: HDC) {
        unsafe {
            let mut rect = RECT::default();
            GetClientRect(self.hwnd, &mut rect);
            let width = rect.right - rect.left;
            let height = rect.bottom - rect.top;

            let mem_dc = CreateCompatibleDC(hdc);
            let mem_bm = CreateCompatibleBitmap(hdc, width, height);
            let old_bm = SelectObject(mem_dc, mem_bm);

            let cfg = self.config.lock().unwrap().clone();
            let app_cfg = &cfg.appearance;

            let bg_col = hex_to_colorref(&app_cfg.bg_color);
            let card_col = hex_to_colorref(&app_cfg.card_bg);
            let sel_col = hex_to_colorref(&app_cfg.selected_bg);
            let accent_col = hex_to_colorref(&app_cfg.accent_color);
            let text_prim = hex_to_colorref(&app_cfg.text_primary);
            let text_sec = hex_to_colorref(&app_cfg.text_secondary);
            let border_col = hex_to_colorref(&app_cfg.border_color);
            let track_col = hex_to_colorref(&app_cfg.track_bg);
            let danger_col = hex_to_colorref(&app_cfg.danger_color);

            // 1. Draw rounded outer frame
            let bg_brush = CreateSolidBrush(COLORREF(bg_col));
            let border_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
            let old_brush = SelectObject(mem_dc, bg_brush);
            let old_pen = SelectObject(mem_dc, border_pen);
            RoundRect(mem_dc, 0, 0, width, height, 18, 18);

            SetBkMode(mem_dc, TRANSPARENT);

            let font_header = create_font("Segoe UI", 12, true);
            let font_title = create_font("Segoe UI", 18, true);
            let font_regular = create_font("Segoe UI", 13, false);
            let font_bold = create_font("Segoe UI", 13, true);
            let font_small = create_font("Segoe UI", 11, false);

            let mut y = 12;

            // 2. Header
            let old_font = SelectObject(mem_dc, font_header);
            let accent_brush = CreateSolidBrush(COLORREF(accent_col));
            SelectObject(mem_dc, accent_brush);
            Ellipse(mem_dc, 16, y + 2, 24, y + 10);

            SetTextColor(mem_dc, COLORREF(text_prim));
            draw_text(mem_dc, "OPEN VOLUME : AUDIO MIXER", 30, y - 2, 200, 18);

            let (_mic_name, _mic_vol, mic_muted) = {
                let mixer = self.mixer.lock().unwrap();
                mixer.get_microphone_info()
            };

            let mic_col = if mic_muted { danger_col } else { accent_col };
            SetTextColor(mem_dc, COLORREF(mic_col));
            let mic_label = if mic_muted { "🎙 MUTED" } else { "🎙 MIC ACTIVE" };
            draw_text(mem_dc, mic_label, width - 110, y - 2, 100, 18);

            y += 20;

            // Device Subtitle
            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            draw_text(mem_dc, "🔊 Speakers (Realtek(R) Audio)", 30, y, width - 40, 16);

            y += 24;

            // 2.5 Toast Notification (Placed between Header and Active Card so it never overlaps!)
            if let Some(ref toast) = self.toast_text {
                if self.toast_time.elapsed() < Duration::from_millis(2200) {
                    let toast_brush = CreateSolidBrush(COLORREF(sel_col));
                    let toast_pen = CreatePen(PS_SOLID, 1, COLORREF(accent_col));
                    SelectObject(mem_dc, toast_brush);
                    SelectObject(mem_dc, toast_pen);
                    RoundRect(mem_dc, 16, y, width - 16, y + 26, 8, 8);
                    DeleteObject(toast_brush);
                    DeleteObject(toast_pen);

                    SelectObject(mem_dc, font_bold);
                    SetTextColor(mem_dc, COLORREF(accent_col));
                    let toast_str = format!("{}  {}", self.toast_icon, toast);
                    draw_text(mem_dc, &toast_str, 24, y + 4, width - 48, 18);

                    y += 34;
                }
            }

            // 3. Active App Card
            let (sel_app, apps_snapshot, sel_idx) = {
                let mixer = self.mixer.lock().unwrap();
                let sel = mixer.get_selected_app().cloned();
                (sel, mixer.get_apps().to_vec(), mixer.get_selected_index())
            };

            if let Some(app) = sel_app {
                let card_brush = CreateSolidBrush(COLORREF(card_col));
                let card_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
                SelectObject(mem_dc, card_brush);
                SelectObject(mem_dc, card_pen);
                RoundRect(mem_dc, 14, y, width - 14, y + 90, 12, 12);

                // Accent indicator bar on card left
                let acc_pen = CreatePen(PS_SOLID, 3, COLORREF(accent_col));
                SelectObject(mem_dc, acc_pen);
                MoveToEx(mem_dc, 14, y + 8, None);
                LineTo(mem_dc, 14, y + 82);

                // App Title
                SelectObject(mem_dc, font_title);
                SetTextColor(mem_dc, COLORREF(text_prim));
                draw_text(mem_dc, &app.name, 26, y + 10, width - 120, 24);

                // Volume % / Muted
                SelectObject(mem_dc, font_bold);
                if app.muted {
                    SetTextColor(mem_dc, COLORREF(danger_col));
                    draw_text(mem_dc, "MUTED", width - 85, y + 14, 60, 20);
                } else {
                    SetTextColor(mem_dc, COLORREF(accent_col));
                    let pct_str = format!("{}%", app.volume);
                    draw_text(mem_dc, &pct_str, width - 75, y + 14, 50, 20);
                }

                // Volume Slider Track
                let bar_x1 = 26;
                let bar_y1 = y + 46;
                let bar_x2 = width - 26;
                let bar_y2 = y + 54;
                let bar_w = bar_x2 - bar_x1;

                let trk_brush = CreateSolidBrush(COLORREF(track_col));
                let trk_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
                SelectObject(mem_dc, trk_brush);
                SelectObject(mem_dc, trk_pen);
                RoundRect(mem_dc, bar_x1, bar_y1, bar_x2, bar_y2, 6, 6);

                // Progress Fill
                if app.volume > 0 && !app.muted {
                    let fill_w = ((bar_w as f32) * (app.volume as f32 / 100.0)).round() as i32;
                    let fill_brush = CreateSolidBrush(COLORREF(accent_col));
                    SelectObject(mem_dc, fill_brush);
                    RoundRect(mem_dc, bar_x1, bar_y1, bar_x1 + fill_w, bar_y2, 6, 6);
                    DeleteObject(fill_brush);
                }

                // Live VU Meter Peak Line
                if self.smoothed_master_peak > 0.01 {
                    let pk_w = ((bar_w as f32) * self.smoothed_master_peak.min(1.0)).round() as i32;
                    let vu_pen = CreatePen(PS_SOLID, 2, COLORREF(0x00FFFFFF)); // Bright white peak line
                    SelectObject(mem_dc, vu_pen);
                    MoveToEx(mem_dc, bar_x1 + pk_w, bar_y1 - 2, None);
                    LineTo(mem_dc, bar_x1 + pk_w, bar_y2 + 2);
                    DeleteObject(vu_pen);
                }

                // Peak Hold Needle
                if self.peak_hold > 0.02 && self.peak_hold > self.smoothed_master_peak {
                    let hold_w = ((bar_w as f32) * self.peak_hold.min(1.0)).round() as i32;
                    let hold_pen = CreatePen(PS_SOLID, 1, COLORREF(0x00FFC4A0));
                    SelectObject(mem_dc, hold_pen);
                    MoveToEx(mem_dc, bar_x1 + hold_w, bar_y1 - 3, None);
                    LineTo(mem_dc, bar_x1 + hold_w, bar_y2 + 3);
                    DeleteObject(hold_pen);
                }

                DeleteObject(card_brush);
                DeleteObject(card_pen);
                DeleteObject(acc_pen);
                DeleteObject(trk_brush);
                DeleteObject(trk_pen);
            }

            y += 100;

            // 4. App List
            let max_visible = app_cfg.max_visible_apps;
            let display_apps = apps_snapshot.iter().enumerate().take(max_visible);

            for (idx, a) in display_apps {
                let is_selected = idx == sel_idx;
                let row_y = y;

                if is_selected {
                    let sel_brush = CreateSolidBrush(COLORREF(sel_col));
                    let sel_pen = CreatePen(PS_SOLID, 1, COLORREF(border_col));
                    SelectObject(mem_dc, sel_brush);
                    SelectObject(mem_dc, sel_pen);
                    RoundRect(mem_dc, 14, row_y, width - 14, row_y + 28, 8, 8);
                    DeleteObject(sel_brush);
                    DeleteObject(sel_pen);

                    SelectObject(mem_dc, font_bold);
                    SetTextColor(mem_dc, COLORREF(text_prim));
                    let prefix = format!("► {}", a.name);
                    draw_text(mem_dc, &prefix, 24, row_y + 4, width - 100, 20);
                } else {
                    SelectObject(mem_dc, font_regular);
                    SetTextColor(mem_dc, COLORREF(text_sec));
                    let prefix = format!("[{}] {}", idx, a.name);
                    draw_text(mem_dc, &prefix, 24, row_y + 4, width - 100, 20);
                }

                // Live Audio Activity Dot
                if idx < self.smoothed_app_peaks.len() && self.smoothed_app_peaks[idx] > 0.015 {
                    let dot_brush = CreateSolidBrush(COLORREF(accent_col));
                    SelectObject(mem_dc, dot_brush);
                    Ellipse(mem_dc, width - 82, row_y + 10, width - 74, row_y + 18);
                    DeleteObject(dot_brush);
                }

                // Volume %
                if a.muted {
                    SetTextColor(mem_dc, COLORREF(danger_col));
                    draw_text(mem_dc, "MUTED", width - 68, row_y + 4, 50, 20);
                } else {
                    SetTextColor(mem_dc, if is_selected { COLORREF(accent_col) } else { COLORREF(text_sec) });
                    let vol_txt = format!("{}%", a.volume);
                    draw_text(mem_dc, &vol_txt, width - 60, row_y + 4, 45, 20);
                }

                y += 32;
            }

            // 6. Footer Controls Hint
            SelectObject(mem_dc, font_small);
            SetTextColor(mem_dc, COLORREF(text_sec));
            let footer = "[8/2] Cycle  [+/-] Vol  [5] Mute  [7/9/3] Media  [NumLk] Exit";
            draw_text(mem_dc, footer, 22, height - 24, width - 40, 18);

            // Blit memory DC to window DC
            BitBlt(hdc, 0, 0, width, height, mem_dc, 0, 0, SRCCOPY);

            // Clean up
            SelectObject(mem_dc, old_bm);
            SelectObject(mem_dc, old_brush);
            SelectObject(mem_dc, old_pen);
            SelectObject(mem_dc, old_font);

            DeleteObject(mem_bm);
            DeleteDC(mem_dc);
            DeleteObject(bg_brush);
            DeleteObject(border_pen);
            DeleteObject(accent_brush);
            DeleteObject(font_header);
            DeleteObject(font_title);
            DeleteObject(font_regular);
            DeleteObject(font_bold);
            DeleteObject(font_small);
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

fn get_primary_work_area() -> (i32, i32, i32, i32) {
    unsafe {
        let mut rect = RECT::default();
        if SystemParametersInfoW(
            SPI_GETWORKAREA,
            0,
            Some(&mut rect as *mut _ as *mut _),
            SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS(0),
        ).is_ok() {
            (
                rect.right - rect.left,
                rect.bottom - rect.top,
                rect.left,
                rect.top,
            )
        } else {
            (1920, 1080, 0, 0)
        }
    }
}

unsafe extern "system" fn overlay_wnd_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_TIMER => {
            if let Some(inst_ptr) = OVERLAY_INSTANCE {
                let inst = &mut *inst_ptr;
                match wparam.0 {
                    TIMER_ANIM_ID => inst.step_animation(),
                    TIMER_VU_ID => inst.poll_vu_meter(),
                    TIMER_AUTOHIDE_ID => inst.check_autohide(),
                    _ => {}
                }
            }
            LRESULT(0)
        }
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            if let Some(inst_ptr) = OVERLAY_INSTANCE {
                let inst = &*inst_ptr;
                inst.paint(hdc);
            }
            EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_ERASEBKGND => LRESULT(1),
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}
