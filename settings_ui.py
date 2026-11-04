import tkinter as tk
from tkinter import ttk, messagebox
import json
import ctypes
from ctypes import wintypes
import time
import os

user32 = ctypes.windll.user32

# Win32 Virtual Key name overrides
VK_NAMES = {
    0x0D: "Enter",
    0x1B: "Esc",
    0x20: "Space",
    0x25: "Left Arrow",
    0x26: "Up Arrow",
    0x27: "Right Arrow",
    0x28: "Down Arrow",
    0x90: "NumLock",
    0x60: "Num 0", 0x61: "Num 1", 0x62: "Num 2", 0x63: "Num 3", 0x64: "Num 4",
    0x65: "Num 5", 0x66: "Num 6", 0x67: "Num 7", 0x68: "Num 8", 0x69: "Num 9",
    0x6A: "Num *", 0x6B: "Num +", 0x6D: "Num -", 0x6E: "Num .", 0x6F: "Num /",
    0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".",
    0xDB: "[", 0xDD: "]", 0xDC: "\\", 0xBA: ";", 0xDE: "'",
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
    0x76: "F7", 0x77: "F8", 0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12"
}

def vk_to_string(vk: int) -> str:
    if vk in VK_NAMES:
        return VK_NAMES[vk]
    # Try system key name
    scan = user32.MapVirtualKeyW(vk, 0)
    buf = ctypes.create_unicode_buffer(32)
    user32.GetKeyNameTextW(scan << 16, buf, 32)
    if buf.value and buf.value.strip():
        return buf.value.strip()
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    return f"Key(0x{vk:02X})"

def format_binding_display(ctrl: bool, alt: bool, shift: bool, win: bool, vk: int) -> str:
    parts = []
    if ctrl: parts.append("Ctrl")
    if alt: parts.append("Alt")
    if shift: parts.append("Shift")
    if win: parts.append("Win")
    parts.append(vk_to_string(vk))
    return " + ".join(parts)

class SettingsWindow:
    """Modern dark-themed Settings & Macro configuration UI for Open Volume."""

    def __init__(self, root: tk.Tk, config_mgr, on_save_callback=None, on_preview_callback=None):
        self.root = root
        self.config_mgr = config_mgr
        self.config = config_mgr.config
        self.on_save = on_save_callback
        self.on_preview = on_preview_callback

        self.win = None
        self.recording_action = None
        self.record_btn_widget = None
        self.active_position_btns = {}
        self.active_color_btns = {}

    def is_open(self) -> bool:
        return self.win is not None and self.win.winfo_exists()

    def show(self):
        if self.is_open():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            return

        self._build_ui()

    def _build_ui(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Open Volume - Settings & Keybindings")
        self.win.geometry("640x740")
        self.win.minsize(580, 680)
        self.win.config(bg="#121318")

        # Set taskbar icon if exists
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.win.iconbitmap(ico_path)
            except Exception:
                pass

        # Center on primary display
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - 640) // 2
        y = (sh - 740) // 2
        self.win.geometry(f"640x740+{x}+{y}")

        # Local edit copy of config
        self.local_cfg = json.loads(json.dumps(self.config))

        # Main scrollable canvas container
        main_frame = tk.Frame(self.win, bg="#121318", padx=20, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header
        header = tk.Frame(main_frame, bg="#121318")
        header.pack(fill=tk.X, pady=(0, 16))

        title_row = tk.Frame(header, bg="#121318")
        title_row.pack(fill=tk.X)

        accent = self.local_cfg.get("appearance", {}).get("accent_color", "#00E5A3")
        tk.Label(
            title_row, text="OPEN VOLUME", fg="#FFFFFF", bg="#121318",
            font=("Segoe UI", 16, "bold")
        ).pack(side=tk.LEFT)

        tk.Label(
            title_row, text=" v1.2.0 ", fg="#121318", bg=accent,
            font=("Segoe UI", 8, "bold"), padx=6, pady=2
        ).pack(side=tk.LEFT, padx=10)

        tk.Label(
            header,
            text="Universal Audio Mixer & Macro Manager for Numpads, TKL, and Laptops",
            fg="#8E90A6", bg="#121318", font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(4, 0))

        # 2. Section: Keyboard Mode
        self._build_mode_section(main_frame)

        # 3. Section: Keybindings & Macros
        self._build_keybindings_section(main_frame)

        # 4. Section: Appearance & HUD Position
        self._build_appearance_section(main_frame)

        # 5. Footer Buttons
        footer = tk.Frame(main_frame, bg="#121318")
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))

        tk.Button(
            footer, text="Reset Defaults", bg="#242838", fg="#8E90A6", activebackground="#2A2D3C",
            activeforeground="#FFFFFF", bd=0, padx=14, pady=8, font=("Segoe UI", 9),
            command=self._reset_defaults
        ).pack(side=tk.LEFT)

        tk.Button(
            footer, text="Save & Apply", bg=accent, fg="#121318", activebackground="#33FFB8",
            activeforeground="#121318", bd=0, padx=20, pady=8, font=("Segoe UI", 10, "bold"),
            command=self._save_and_apply
        ).pack(side=tk.RIGHT)

        tk.Button(
            footer, text="Preview HUD", bg="#1A1B24", fg="#FFFFFF", activebackground="#242838",
            activeforeground="#FFFFFF", bd=1, highlightbackground="#2A2D3C", padx=14, pady=8,
            font=("Segoe UI", 9), command=self._trigger_preview
        ).pack(side=tk.RIGHT, padx=10)

        # Global key press binding for recording
        self.win.bind("<KeyPress>", self._on_key_press)
        self.win.bind("<Button-1>", self._on_click_outside)

    def _build_mode_section(self, parent):
        card = tk.Frame(parent, bg="#1A1B24", padx=14, pady=12, bd=1, highlightbackground="#2A2D3C", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 14))

        tk.Label(card, text="KEYBOARD MODE", fg="#8E90A6", bg="#1A1B24", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))

        modes_frame = tk.Frame(card, bg="#1A1B24")
        modes_frame.pack(fill=tk.X)

        self.mode_var = tk.StringVar(value=self.local_cfg.get("mode", "hybrid"))

        modes = [
            ("hybrid", "⚡ Hybrid Mode (All Keyboards)", "Numpad keys + custom shortcuts both work"),
            ("numpad", "🔢 Numpad Only", "Everest 60, Full-Size, or External USB Numpad"),
            ("custom", "⌨️ Compact / TKL Mode", "60%/75%/TKL/Laptops (No numpad needed)")
        ]

        for val, label, subtext in modes:
            row = tk.Frame(modes_frame, bg="#1A1B24")
            row.pack(fill=tk.X, pady=3)
            rb = tk.Radiobutton(
                row, text=label, variable=self.mode_var, value=val,
                bg="#1A1B24", fg="#FFFFFF", selectcolor="#242838",
                activebackground="#1A1B24", activeforeground="#00E5A3",
                font=("Segoe UI", 9, "bold"), command=self._on_mode_change
            )
            rb.pack(side=tk.LEFT)
            tk.Label(row, text=f" - {subtext}", fg="#8E90A6", bg="#1A1B24", font=("Segoe UI", 8)).pack(side=tk.LEFT)

    def _build_keybindings_section(self, parent):
        card = tk.Frame(parent, bg="#1A1B24", padx=14, pady=12, bd=1, highlightbackground="#2A2D3C", highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 14))

        header_row = tk.Frame(card, bg="#1A1B24")
        header_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(header_row, text="CUSTOM SHORTCUTS & MACROS", fg="#8E90A6", bg="#1A1B24", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self.record_status_lbl = tk.Label(header_row, text="", fg="#00E5A3", bg="#1A1B24", font=("Segoe UI", 8, "bold"))
        self.record_status_lbl.pack(side=tk.RIGHT)

        self.bindings_container = tk.Frame(card, bg="#1A1B24")
        self.bindings_container.pack(fill=tk.X)

        self._refresh_binding_rows()

    def _refresh_binding_rows(self):
        for w in self.bindings_container.winfo_children():
            w.destroy()

        bindings_cfg = self.local_cfg.get("custom_bindings", {})

        action_labels = [
            ("toggle_layer", "Toggle HUD Layer", "Global shortcut to open/close overlay"),
            ("volume_up", "Volume Up (+)", "Increase volume of selected app"),
            ("volume_down", "Volume Down (-)", "Decrease volume of selected app"),
            ("next_app", "Next App", "Cycle to next audio application"),
            ("prev_app", "Previous App", "Cycle to previous audio application"),
            ("toggle_mute", "Toggle Mute", "Mute or unmute selected application"),
            ("exit_layer", "Exit HUD", "Dismiss overlay immediately")
        ]

        self.btn_map = {}

        for act_key, act_name, desc in action_labels:
            row = tk.Frame(self.bindings_container, bg="#1A1B24", pady=3)
            row.pack(fill=tk.X)

            info = tk.Frame(row, bg="#1A1B24")
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(info, text=act_name, fg="#FFFFFF", bg="#1A1B24", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(info, text=desc, fg="#8E90A6", bg="#1A1B24", font=("Segoe UI", 8)).pack(anchor="w")

            b_data = bindings_cfg.get(act_key, {})
            disp = b_data.get("display", "None")

            btn = tk.Button(
                row, text=disp, bg="#242838", fg="#00E5A3", activebackground="#2A2D3C",
                activeforeground="#33FFB8", bd=1, highlightbackground="#2A2D3C",
                padx=12, pady=4, font=("Segoe UI", 9, "bold"), width=16,
                command=lambda a=act_key: self._start_recording(a)
            )
            btn.pack(side=tk.RIGHT)
            self.btn_map[act_key] = btn

    def _build_appearance_section(self, parent):
        card = tk.Frame(parent, bg="#1A1B24", padx=14, pady=12, bd=1, highlightbackground="#2A2D3C", highlightthickness=1)
        card.pack(fill=tk.X)

        tk.Label(card, text="HUD POSITION & ANIMATION", fg="#8E90A6", bg="#1A1B24", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 10))

        content_frame = tk.Frame(card, bg="#1A1B24")
        content_frame.pack(fill=tk.X)

        # Left Column: Position Grid
        pos_frame = tk.Frame(content_frame, bg="#1A1B24")
        pos_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        tk.Label(pos_frame, text="Screen Anchor:", fg="#FFFFFF", bg="#1A1B24", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        grid = tk.Frame(pos_frame, bg="#1A1B24")
        grid.pack()

        current_pos = self.local_cfg.get("appearance", {}).get("position", "bottom-right")

        pos_grid = [
            [("top-left", "Top Left"), ("top-center", "Top Center"), ("top-right", "Top Right")],
            [("center-left", "Mid Left"), ("center", "Center"), ("center-right", "Mid Right")],
            [("bottom-left", "Bottom Left"), ("bottom-center", "Bottom Center"), ("bottom-right", "Bottom Right")]
        ]

        self.pos_buttons = {}
        for r_idx, row in enumerate(pos_grid):
            for c_idx, (p_val, p_lbl) in enumerate(row):
                btn = tk.Button(
                    grid, text=p_lbl, font=("Segoe UI", 8), width=11, pady=4, bd=1,
                    command=lambda p=p_val: self._select_position(p)
                )
                btn.grid(row=r_idx, column=c_idx, padx=2, pady=2)
                self.pos_buttons[p_val] = btn

        self._refresh_position_buttons(current_pos)

        # Right Column: Animation & Colors
        right_col = tk.Frame(content_frame, bg="#1A1B24")
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Animation toggle
        self.anim_var = tk.BooleanVar(value=self.local_cfg.get("appearance", {}).get("animation_enabled", True))
        anim_cb = tk.Checkbutton(
            right_col, text="Smooth Slide & Fade Animation", variable=self.anim_var,
            bg="#1A1B24", fg="#FFFFFF", selectcolor="#242838", activebackground="#1A1B24",
            activeforeground="#00E5A3", font=("Segoe UI", 9)
        )
        anim_cb.pack(anchor="w", pady=(4, 4))

        # Startup toggle
        import startup_manager
        current_startup = startup_manager.is_startup_enabled()
        self.startup_var = tk.BooleanVar(value=current_startup)
        startup_cb = tk.Checkbutton(
            right_col, text="Start with Windows on Boot", variable=self.startup_var,
            bg="#1A1B24", fg="#FFFFFF", selectcolor="#242838", activebackground="#1A1B24",
            activeforeground="#00E5A3", font=("Segoe UI", 9)
        )
        startup_cb.pack(anchor="w", pady=(0, 10))

        # Accent Color Palette
        tk.Label(right_col, text="Accent Theme:", fg="#FFFFFF", bg="#1A1B24", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        palette_frame = tk.Frame(right_col, bg="#1A1B24")
        palette_frame.pack(anchor="w")

        colors = [
            ("#00E5A3", "Mint"),
            ("#38BDF8", "Sky"),
            ("#A855F7", "Purple"),
            ("#F97316", "Orange"),
            ("#EF4444", "Crimson")
        ]

        self.color_buttons = {}
        curr_accent = self.local_cfg.get("appearance", {}).get("accent_color", "#00E5A3")

        for c_hex, c_name in colors:
            btn = tk.Button(
                palette_frame, text="  ", bg=c_hex, activebackground=c_hex, bd=2,
                relief=tk.SOLID if curr_accent.upper() == c_hex.upper() else tk.FLAT,
                width=3, height=1, command=lambda c=c_hex: self._select_accent_color(c)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.color_buttons[c_hex] = btn

    def _refresh_position_buttons(self, selected_pos):
        accent = self.local_cfg.get("appearance", {}).get("accent_color", "#00E5A3")
        for p_val, btn in self.pos_buttons.items():
            if p_val == selected_pos:
                btn.config(bg=accent, fg="#121318", font=("Segoe UI", 8, "bold"))
            else:
                btn.config(bg="#242838", fg="#FFFFFF", font=("Segoe UI", 8))

    def _select_position(self, p_val):
        self.local_cfg.setdefault("appearance", {})["position"] = p_val
        self._refresh_position_buttons(p_val)

    def _select_accent_color(self, c_hex):
        self.local_cfg.setdefault("appearance", {})["accent_color"] = c_hex
        for ch, btn in self.color_buttons.items():
            btn.config(relief=tk.SOLID if ch.upper() == c_hex.upper() else tk.FLAT)
        curr_pos = self.local_cfg.get("appearance", {}).get("position", "bottom-right")
        self._refresh_position_buttons(curr_pos)

    def _start_recording(self, action_key):
        if self.recording_action:
            prev_btn = self.btn_map.get(self.recording_action)
            if prev_btn:
                prev_disp = self.local_cfg.get("custom_bindings", {}).get(self.recording_action, {}).get("display", "None")
                prev_btn.config(text=prev_disp, bg="#242838", fg="#00E5A3")

        self.recording_action = action_key
        btn = self.btn_map.get(action_key)
        if btn:
            btn.config(text="[ Press Key... ]", bg="#F97316", fg="#121318")
        self.record_status_lbl.config(text="Recording: Press any key combo (Esc to cancel)...", fg="#F97316")
        self.win.focus_set()

    def _on_key_press(self, event):
        if not self.recording_action:
            return

        vk = event.keycode
        # Ignore lone modifier presses
        if vk in (0x11, 0x12, 0x10, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
            return

        # Cancel on Escape if recording an action other than exit_layer
        if vk == 0x1B and self.recording_action != "exit_layer":
            self._cancel_recording()
            return

        ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
        alt = bool(user32.GetAsyncKeyState(0x12) & 0x8000)
        shift = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
        win = bool(user32.GetAsyncKeyState(0x5B) & 0x8000) or bool(user32.GetAsyncKeyState(0x5C) & 0x8000)

        disp = format_binding_display(ctrl, alt, shift, win, vk)

        # Save to local_cfg
        if "custom_bindings" not in self.local_cfg:
            self.local_cfg["custom_bindings"] = {}

        self.local_cfg["custom_bindings"][self.recording_action] = {
            "vk": vk,
            "ctrl": ctrl,
            "alt": alt,
            "shift": shift,
            "win": win,
            "display": disp
        }

        btn = self.btn_map.get(self.recording_action)
        if btn:
            btn.config(text=disp, bg="#242838", fg="#00E5A3")

        self.record_status_lbl.config(text=f"Set: {disp}", fg="#00E5A3")
        self.recording_action = None

    def _cancel_recording(self):
        if self.recording_action:
            btn = self.btn_map.get(self.recording_action)
            if btn:
                disp = self.local_cfg.get("custom_bindings", {}).get(self.recording_action, {}).get("display", "None")
                btn.config(text=disp, bg="#242838", fg="#00E5A3")
            self.recording_action = None
            self.record_status_lbl.config(text="")

    def _on_click_outside(self, event):
        # If user clicks outside the recording button, cancel recording
        if self.recording_action:
            btn = self.btn_map.get(self.recording_action)
            if btn and event.widget != btn:
                self._cancel_recording()

    def _on_mode_change(self):
        new_mode = self.mode_var.get()
        self.local_cfg["mode"] = new_mode

    def _reset_defaults(self):
        from config_manager import DEFAULT_CONFIG
        self.local_cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        self.mode_var.set(self.local_cfg.get("mode", "hybrid"))
        if hasattr(self, "startup_var"):
            self.startup_var.set(False)
        self._refresh_binding_rows()
        curr_pos = self.local_cfg.get("appearance", {}).get("position", "bottom-right")
        self._refresh_position_buttons(curr_pos)
        self.record_status_lbl.config(text="Reset to default settings", fg="#00E5A3")

    def _trigger_preview(self):
        if self.on_preview:
            # Pass temporary local config for preview
            self.on_preview(self.local_cfg)

    def _save_and_apply(self):
        self.local_cfg["mode"] = self.mode_var.get()
        self.local_cfg.setdefault("appearance", {})["animation_enabled"] = self.anim_var.get()

        # Update startup setting
        import startup_manager
        startup_desired = self.startup_var.get()
        self.local_cfg.setdefault("behavior", {})["start_on_boot"] = startup_desired
        startup_manager.set_startup_enabled(startup_desired)

        # Update manager config and save to disk
        self.config_mgr.config = self.local_cfg
        self.config_mgr.save()

        if self.on_save:
            self.on_save(self.local_cfg)

        self.record_status_lbl.config(text="Settings saved & applied successfully!", fg="#00E5A3")
        self.win.after(600, self.win.destroy)
