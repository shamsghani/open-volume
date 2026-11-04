import tkinter as tk
from tkinter import font as tkfont
import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

def get_primary_work_area() -> RECT:
    """Gets the work area of the primary display (excluding the Windows taskbar)."""
    rc = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)  # SPI_GETWORKAREA
    return rc

class OverlayWidget:
    """A floating, always-on-top, non-activating HUD overlay widget for the Numpad Audio Layer."""

    def __init__(self, root: tk.Tk, config: dict, on_timeout_callback=None):
        self.root = root
        self.config = config
        self.on_timeout = on_timeout_callback

        self.visible = False
        self.apps = []
        self.selected_index = 0
        self.last_activity_time = 0
        self.auto_hide_seconds = config.get("behavior", {}).get("auto_hide_seconds", 6)

        # Style colors
        app_cfg = config.get("appearance", {})
        self.accent_color = app_cfg.get("accent_color", "#00E5A3")
        self.bg_color = app_cfg.get("bg_color", "#121318")
        self.card_bg = app_cfg.get("card_bg", "#1A1B24")
        self.selected_bg = app_cfg.get("selected_bg", "#242838")
        self.text_primary = app_cfg.get("text_primary", "#FFFFFF")
        self.text_secondary = app_cfg.get("text_secondary", "#8E90A6")
        self.border_color = app_cfg.get("border_color", "#2A2D3C")
        self.track_bg = app_cfg.get("track_bg", "#272A38")
        self.danger_color = app_cfg.get("danger_color", "#FF4B5C")
        self.badge_text = app_cfg.get("badge_text", "#121318")
        self.width = app_cfg.get("width", 360)
        self.margin_x = app_cfg.get("margin_x", 28)
        self.margin_y = app_cfg.get("margin_y", 60)
        self.max_visible_apps = app_cfg.get("max_visible_apps", 6)

        # Position and Animation settings
        self.position = app_cfg.get("position", "bottom-right")
        self.animation_enabled = app_cfg.get("animation_enabled", True)
        self.animation_duration = app_cfg.get("animation_duration_ms", 180) / 1000.0
        self.anim_in_progress = False
        self.anim_token = 0

        self.target_x = 0
        self.target_y = 0
        self.target_h = 120
        self.slide_dx = 0
        self.slide_dy = 0

        # Window setup
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg=self.bg_color)

        # Canvas for custom rendering
        self.canvas = tk.Canvas(
            self.win,
            bg=self.bg_color,
            highlightthickness=1,
            highlightbackground=self.border_color,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Win32 non-activating style so it never steals window focus
        self._apply_no_activate_style()

        # Timer loop for auto-hide
        self._check_timer()

    def _get_toplevel_hwnd(self) -> int:
        """Returns the real top-level Win32 HWND for the Tkinter Toplevel window."""
        try:
            self.win.update_idletasks()
            frame_hex = self.win.wm_frame()
            if frame_hex:
                return int(frame_hex, 16)
        except Exception:
            pass
        inner = self.win.winfo_id()
        parent = user32.GetParent(inner)
        return parent if parent else inner

    def _apply_no_activate_style(self):
        """Sets WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW and WS_EX_TOPMOST so the HUD never unfocuses active games/windows."""
        try:
            hwnd = self._get_toplevel_hwnd()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TOPMOST = 0x00000008

            old_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = old_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

            # Re-assert TOPMOST & NOACTIVATE via SetWindowPos
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception as e:
            print(f"[Overlay] Error setting no-activate style: {e}")

    def calculate_position(self, height: int):
        """Calculates the target (x, y) coordinates and slide offsets based on configured anchor."""
        work_area = get_primary_work_area()
        work_w = work_area.right - work_area.left
        work_h = work_area.bottom - work_area.top
        pos = self.position.lower().replace("_", "-").strip()

        # Horizontal alignment & slide delta
        if "left" in pos:
            x = work_area.left + self.margin_x
            slide_dx = -24
        elif "right" in pos:
            x = work_area.right - self.width - self.margin_x
            slide_dx = 24
        else:  # center / mid
            x = work_area.left + (work_w - self.width) // 2
            slide_dx = 0

        # Vertical alignment & slide delta
        if "top" in pos:
            y = work_area.top + self.margin_y
            slide_dy = -24
        elif "bottom" in pos:
            y = work_area.bottom - height - self.margin_y
            slide_dy = 24
        else:  # center / mid
            y = work_area.top + (work_h - height) // 2
            slide_dy = 0

        # If it's center on both axes, slide up gently
        if slide_dx == 0 and slide_dy == 0:
            slide_dy = 20

        return x, y, slide_dx, slide_dy

    def set_position(self, new_position: str):
        """Updates the widget anchor position dynamically."""
        self.position = new_position
        if self.visible:
            self.render()

    def update_appearance(self, app_cfg: dict):
        """Dynamically updates theme colors, geometry, and styling."""
        self.accent_color = app_cfg.get("accent_color", self.accent_color)
        self.bg_color = app_cfg.get("bg_color", self.bg_color)
        self.card_bg = app_cfg.get("card_bg", self.card_bg)
        self.selected_bg = app_cfg.get("selected_bg", self.selected_bg)
        self.text_primary = app_cfg.get("text_primary", self.text_primary)
        self.text_secondary = app_cfg.get("text_secondary", self.text_secondary)
        self.border_color = app_cfg.get("border_color", self.border_color)
        self.track_bg = app_cfg.get("track_bg", self.track_bg)
        self.danger_color = app_cfg.get("danger_color", self.danger_color)
        self.badge_text = app_cfg.get("badge_text", self.badge_text)

        if "position" in app_cfg:
            self.position = app_cfg["position"]
        if "animation_enabled" in app_cfg:
            self.animation_enabled = app_cfg["animation_enabled"]
        if "animation_duration_ms" in app_cfg:
            self.animation_duration = app_cfg["animation_duration_ms"] / 1000.0

        self.win.config(bg=self.bg_color)
        self.canvas.config(bg=self.bg_color, highlightbackground=self.border_color)
        if self.visible:
            self.render()

    def _reposition(self, height: int):
        self.target_h = height
        self.target_x, self.target_y, self.slide_dx, self.slide_dy = self.calculate_position(height)
        if not self.anim_in_progress:
            self.win.geometry(f"{self.width}x{height}+{self.target_x}+{self.target_y}")

    def show(self, animate: bool = True):
        self.visible = True
        self.last_activity_time = time.time()
        self.render()

        if not self.animation_enabled or not animate:
            self.anim_in_progress = False
            self.win.attributes("-alpha", 1.0)
            self.win.geometry(f"{self.width}x{self.target_h}+{self.target_x}+{self.target_y}")
            self.win.deiconify()
            self.win.lift()
            self.win.attributes("-topmost", True)
            self._apply_no_activate_style()
            self.win.update_idletasks()
            return

        # Start slide-in and fade-in animation
        self.anim_token += 1
        token = self.anim_token
        self.anim_in_progress = True

        start_x = self.target_x + self.slide_dx
        start_y = self.target_y + self.slide_dy
        self.win.attributes("-alpha", 0.05)
        self.win.geometry(f"{self.width}x{self.target_h}+{start_x}+{start_y}")
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        self._apply_no_activate_style()
        self.win.update_idletasks()

        start_time = time.time()
        self._step_animate_in(token, start_time)

    def _step_animate_in(self, token: int, start_time: float):
        if token != self.anim_token or not self.visible:
            return

        elapsed = time.time() - start_time
        t = min(1.0, elapsed / max(0.01, self.animation_duration))
        # Cubic ease-out
        ease = 1.0 - (1.0 - t) ** 3

        cur_x = int(self.target_x + self.slide_dx * (1.0 - ease))
        cur_y = int(self.target_y + self.slide_dy * (1.0 - ease))
        cur_alpha = min(1.0, 0.05 + 0.95 * ease)

        self.win.geometry(f"{self.width}x{self.target_h}+{cur_x}+{cur_y}")
        self.win.attributes("-alpha", cur_alpha)
        self.win.update_idletasks()

        if t < 1.0:
            self.root.after(16, lambda: self._step_animate_in(token, start_time))
        else:
            self.anim_in_progress = False
            self.win.geometry(f"{self.width}x{self.target_h}+{self.target_x}+{self.target_y}")
            self.win.attributes("-alpha", 1.0)

    def hide(self, animate: bool = True):
        if not self.visible:
            return

        self.visible = False

        if not self.animation_enabled or not animate:
            self.anim_token += 1
            self.anim_in_progress = False
            self.win.withdraw()
            return

        # Start slide-out and fade-out animation
        self.anim_token += 1
        token = self.anim_token
        self.anim_in_progress = True

        start_time = time.time()
        fade_duration = min(0.12, self.animation_duration * 0.7)
        self._step_animate_out(token, start_time, fade_duration)

    def _step_animate_out(self, token: int, start_time: float, duration: float):
        if token != self.anim_token:
            return

        elapsed = time.time() - start_time
        t = min(1.0, elapsed / max(0.01, duration))
        # Cubic ease-in
        ease = t ** 3

        cur_x = int(self.target_x + self.slide_dx * ease)
        cur_y = int(self.target_y + self.slide_dy * ease)
        cur_alpha = max(0.0, 1.0 - ease)

        self.win.geometry(f"{self.width}x{self.target_h}+{cur_x}+{cur_y}")
        self.win.attributes("-alpha", cur_alpha)
        self.win.update_idletasks()

        if t < 1.0:
            self.root.after(16, lambda: self._step_animate_out(token, start_time, duration))
        else:
            self.anim_in_progress = False
            self.visible = False
            self.win.withdraw()

    def is_visible(self) -> bool:
        return self.visible

    def reset_timer(self):
        self.last_activity_time = time.time()

    def update_data(self, apps: list, selected_index: int):
        self.apps = apps
        self.selected_index = selected_index
        self.reset_timer()
        if self.visible:
            self.render()

    def _check_timer(self):
        if self.visible and self.auto_hide_seconds > 0:
            if time.time() - self.last_activity_time > self.auto_hide_seconds:
                if self.on_timeout:
                    self.on_timeout()
                else:
                    self.hide()
        self.root.after(200, self._check_timer)

    def render(self):
        self.canvas.delete("all")
        if not self.apps:
            height = 120
            self._reposition(height)
            self.canvas.create_text(
                self.width // 2, 60,
                text="No active audio apps found",
                fill=self.text_secondary,
                font=("Segoe UI", 11)
            )
            return

        sel_app = self.apps[self.selected_index] if 0 <= self.selected_index < len(self.apps) else self.apps[0]

        # Dynamic height calculation
        list_count = min(len(self.apps), self.max_visible_apps)
        height = 48 + 98 + (list_count * 32) + 40
        self._reposition(height)

        y = 12

        # 1. Header
        self.canvas.create_oval(18, y + 4, 26, y + 12, fill=self.accent_color, outline="")
        self.canvas.create_text(
            34, y + 8,
            anchor="w",
            text="NUMPAD LAYER 2 : AUDIO MIXER",
            fill=self.text_primary,
            font=("Segoe UI", 9, "bold")
        )
        self.canvas.create_text(
            self.width - 18, y + 8,
            anchor="e",
            text="ACTIVE",
            fill=self.accent_color,
            font=("Segoe UI", 8, "bold")
        )
        y += 28

        # 2. Main Focus Card (Selected App)
        card_x1, card_y1 = 14, y
        card_x2, card_y2 = self.width - 14, y + 90
        # Card background
        self.canvas.create_rectangle(
            card_x1, card_y1, card_x2, card_y2,
            fill=self.card_bg, outline=self.border_color, width=1
        )
        # Left accent stripe
        self.canvas.create_rectangle(
            card_x1, card_y1, card_x1 + 4, card_y2,
            fill=self.accent_color, outline=""
        )

        # Selected App Name
        app_name = sel_app['name']
        if len(app_name) > 24:
            app_name = app_name[:22] + "..."
        self.canvas.create_text(
            card_x1 + 16, card_y1 + 22,
            anchor="w",
            text=app_name,
            fill=self.text_primary,
            font=("Segoe UI", 13, "bold")
        )

        # Volume Badge / Mute status
        if sel_app['muted']:
            vol_badge = "MUTED"
            badge_color = self.danger_color
        else:
            vol_badge = f"{sel_app['volume']}%"
            badge_color = self.accent_color

        self.canvas.create_text(
            card_x2 - 16, card_y1 + 22,
            anchor="e",
            text=vol_badge,
            fill=badge_color,
            font=("Segoe UI", 12, "bold")
        )

        # Progress Bar
        bar_x1 = card_x1 + 16
        bar_y1 = card_y1 + 52
        bar_x2 = card_x2 - 16
        bar_y2 = bar_y1 + 14

        # Track background
        self.canvas.create_rectangle(
            bar_x1, bar_y1, bar_x2, bar_y2,
            fill=self.track_bg, outline=""
        )
        # Fill
        fill_width = int((bar_x2 - bar_x1) * (sel_app['volume'] / 100.0))
        if fill_width > 0:
            fill_color = self.danger_color if sel_app['muted'] else self.accent_color
            self.canvas.create_rectangle(
                bar_x1, bar_y1, bar_x1 + fill_width, bar_y2,
                fill=fill_color, outline=""
            )

        y += 102

        # 3. Compact App List
        start_idx = 0
        if len(self.apps) > self.max_visible_apps:
            start_idx = max(0, min(self.selected_index - 2, len(self.apps) - self.max_visible_apps))

        end_idx = min(start_idx + self.max_visible_apps, len(self.apps))

        for idx in range(start_idx, end_idx):
            item = self.apps[idx]
            is_sel = (idx == self.selected_index)

            row_y1 = y
            row_y2 = y + 28
            row_x1 = 14
            row_x2 = self.width - 14

            if is_sel:
                self.canvas.create_rectangle(
                    row_x1, row_y1, row_x2, row_y2,
                    fill=self.selected_bg, outline=""
                )
                marker = "► "
                name_color = self.text_primary
                font_weight = "bold"
            else:
                marker = f"[{idx}] " if idx < 10 else "   "
                name_color = self.text_secondary
                font_weight = "normal"

            # Name
            row_name = item['name']
            if len(row_name) > 22:
                row_name = row_name[:20] + "..."
            self.canvas.create_text(
                row_x1 + 10, row_y1 + 14,
                anchor="w",
                text=f"{marker}{row_name}",
                fill=name_color,
                font=("Segoe UI", 9, font_weight)
            )

            # Vol text
            row_vol_text = "MUTED" if item['muted'] else f"{item['volume']}%"
            row_vol_color = self.danger_color if item['muted'] else (self.accent_color if is_sel else self.text_secondary)
            self.canvas.create_text(
                row_x2 - 10, row_y1 + 14,
                anchor="e",
                text=row_vol_text,
                fill=row_vol_color,
                font=("Segoe UI", 9, "bold" if is_sel else "normal")
            )

            y += 32

        # 4. Footer shortcuts legend
        y += 6
        self.canvas.create_line(14, y, self.width - 14, y, fill="#232530")
        y += 12
        legend = "[8/2] Cycle   [+/-] Vol   [5] Mute   [NumLk] Exit"
        self.canvas.create_text(
            self.width // 2, y,
            anchor="center",
            text=legend,
            fill=self.text_secondary,
            font=("Segoe UI", 8)
        )
