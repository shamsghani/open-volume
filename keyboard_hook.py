import ctypes
from ctypes import wintypes
import os
import sys
import threading
import time
import winsound
from sound_generator import ensure_sound_assets, SoundEngine

# Win32 Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

# Virtual Key Codes
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

# Numpad Keys
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
VK_NUMPAD4 = 0x64
VK_NUMPAD5 = 0x65
VK_NUMPAD6 = 0x66
VK_NUMPAD7 = 0x67
VK_NUMPAD8 = 0x68
VK_NUMPAD9 = 0x69
VK_MULTIPLY = 0x6A  # *
VK_ADD = 0x6B       # +
VK_SUBTRACT = 0x6D  # -
VK_DECIMAL = 0x6E   # .
VK_DIVIDE = 0x6F    # /
VK_NUMLOCK = 0x90

# Standard Keyboard +/- for convenience
VK_OEM_PLUS = 0xBB
VK_OEM_MINUS = 0xBD

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

# Setup Win32 Function Prototypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_longlong
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK

user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL

class NumpadLayerHook:
    """Manages low-level Windows keyboard hooking and Layer 2 state."""

    def __init__(self, config: dict, callbacks: dict):
        self.config = config
        self.callbacks = callbacks  # dict of action -> callable

        self.layer_active = False
        self.hook_handle = None
        self.thread_id = None
        self.worker_thread = None
        self._c_callback = None  # keep reference to prevent GC

        self.last_numlock_press = 0.0
        self.sound_enabled = config.get("volume", {}).get("sound_feedback", True)
        self.ctrl_down = False
        self.alt_down = False
        self.shift_down = False
        self.numlock_is_down = False
        self.multiply_is_down = False

        # Pre-synthesize warm, round womp sounds and initialize 8-voice polyphonic engine
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        self.sounds_dir = ensure_sound_assets(base_dir)
        self.sound_engine = SoundEngine(self.sounds_dir, num_voices=8)

        # Strictly numpad keys that should be suppressed when layer is active
        # Notice: Main keyboard Enter, Main keyboard -/+, and arrow keys are NOT here!
        self.suppressed_vks = set([
            VK_ADD, VK_SUBTRACT, VK_MULTIPLY, VK_DIVIDE,
            VK_NUMPAD0, VK_NUMPAD1, VK_NUMPAD2, VK_NUMPAD3, VK_NUMPAD4,
            VK_NUMPAD5, VK_NUMPAD6, VK_NUMPAD7, VK_NUMPAD8, VK_NUMPAD9,
            VK_DECIMAL, VK_NUMLOCK
        ])

    def start(self):
        """Starts hook in a background thread."""
        self.worker_thread = threading.Thread(target=self._hook_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Removes hook and stops message loop."""
        if hasattr(self, "sound_engine"):
            self.sound_engine.close()
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)  # WM_QUIT
        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None

    def update_config(self, new_config: dict):
        """Updates hook settings and active custom bindings dynamically."""
        self.config = new_config
        self.sound_enabled = new_config.get("volume", {}).get("sound_feedback", True)

    def _matches_binding(self, binding_dict: dict, vk: int, ctrl: bool, alt: bool, shift: bool, win: bool) -> bool:
        if not binding_dict:
            return False
        b_vk = binding_dict.get("vk")
        if b_vk != vk:
            return False
        return (
            bool(binding_dict.get("ctrl", False)) == ctrl
            and bool(binding_dict.get("alt", False)) == alt
            and bool(binding_dict.get("shift", False)) == shift
            and bool(binding_dict.get("win", False)) == win
        )

    def is_layer_active(self) -> bool:
        return self.layer_active

    def set_layer_active(self, active: bool):
        if self.layer_active != active:
            self.layer_active = active
            print(f"[Hook] Layer 2 state changed -> {'ACTIVE' if active else 'INACTIVE'}")
            if active:
                self._play_sound("enter")
                if "on_layer_enter" in self.callbacks:
                    self.callbacks["on_layer_enter"]()
            else:
                self._play_sound("exit")
                if "on_layer_exit" in self.callbacks:
                    self.callbacks["on_layer_exit"]()

    def _play_sound(self, sound_type: str = "cycle"):
        """Plays smooth, polyphonic zero-latency audio feedback without cut-outs."""
        if not self.sound_enabled:
            return
        try:
            self.sound_engine.play(sound_type)
        except Exception:
            pass

    def _hook_loop(self):
        # Attach worker thread to Default desktop so hook receives system-wide events
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                print("[Hook] Worker thread attached to 'Default' desktop.")
        except Exception as e:
            print(f"[Hook] Error attaching to Default desktop: {e}")

        self.thread_id = kernel32.GetCurrentThreadId()

        def _hook_proc(nCode, wParam, lParam):
            if nCode < 0:
                return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

            try:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                vk = kb.vkCode

                is_keydown = (wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN)
                is_keyup = (wParam == WM_KEYUP or wParam == WM_SYSKEYUP)
                is_extended = bool(kb.flags & 1)

                # Track modifier key states directly
                if is_keydown:
                    if vk in (VK_CONTROL, 0xA2, 0xA3):  # VK_CONTROL, VK_LCONTROL, VK_RCONTROL
                        self.ctrl_down = True
                    elif vk in (VK_MENU, 0xA4, 0xA5):   # VK_MENU, VK_LMENU, VK_RMENU
                        self.alt_down = True
                    elif vk in (VK_SHIFT, 0xA0, 0xA1):  # VK_SHIFT, VK_LSHIFT, VK_RSHIFT
                        self.shift_down = True
                elif is_keyup:
                    if vk in (VK_CONTROL, 0xA2, 0xA3):
                        self.ctrl_down = False
                    elif vk in (VK_MENU, 0xA4, 0xA5):
                        self.alt_down = False
                    elif vk in (VK_SHIFT, 0xA0, 0xA1):
                        self.shift_down = False
                    elif vk == VK_NUMLOCK:
                        self.numlock_is_down = False
                    elif vk == VK_MULTIPLY:
                        self.multiply_is_down = False

                ctrl_is_active = (
                    self.ctrl_down
                    or bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                    or bool(user32.GetAsyncKeyState(0xA2) & 0x8000)
                    or bool(user32.GetAsyncKeyState(0xA3) & 0x8000)
                )

                shift_is_active = (
                    self.shift_down
                    or bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                )

                alt_is_active = (
                    self.alt_down
                    or bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                )

                win_is_active = (
                    bool(user32.GetAsyncKeyState(0x5B) & 0x8000)
                    or bool(user32.GetAsyncKeyState(0x5C) & 0x8000)
                )

                mode = self.config.get("mode", "hybrid")
                custom_bindings = self.config.get("custom_bindings", {})

                # --- 1. TOGGLE LAYER 2 CHECK ---
                # Check custom toggle hotkey (e.g. Ctrl + Alt + V)
                if is_keydown and mode in ("hybrid", "custom"):
                    toggle_b = custom_bindings.get("toggle_layer", {})
                    if self._matches_binding(toggle_b, vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                        print(f"[Hook] Trigger detected: Custom Toggle ({toggle_b.get('display', 'Hotkey')})")
                        self.set_layer_active(not self.layer_active)
                        return 1

                # Check Numpad toggles (Ctrl + NumLock, Double-tap NumLock, Ctrl + Numpad *)
                if mode in ("hybrid", "numpad") and is_keydown and (vk == VK_NUMLOCK or (ctrl_is_active and vk == VK_MULTIPLY)):
                    # Check for autorepeat debounce: ignore repeated down events while holding
                    if vk == VK_NUMLOCK:
                        if self.numlock_is_down:
                            return 1 if self.layer_active else 0
                        self.numlock_is_down = True
                    elif vk == VK_MULTIPLY:
                        if self.multiply_is_down:
                            return 1 if self.layer_active else 0
                        self.multiply_is_down = True

                    now = time.time()
                    double_tap_allowed = self.config.get("hotkey", {}).get("double_tap_numlock", True)
                    max_interval = self.config.get("hotkey", {}).get("double_tap_max_interval_ms", 400) / 1000.0

                    # Trigger: Ctrl + NumLock or Ctrl + Numpad *
                    if ctrl_is_active:
                        print(f"[Hook] Trigger detected: Ctrl + { 'NumLock' if vk == VK_NUMLOCK else 'Multiply' }")
                        self.set_layer_active(not self.layer_active)
                        return 1  # Suppress NumLock/Multiply

                    # Trigger: Double-tap NumLock
                    if vk == VK_NUMLOCK and double_tap_allowed and (now - self.last_numlock_press <= max_interval):
                        print("[Hook] Trigger detected: Double-tap NumLock")
                        self.set_layer_active(not self.layer_active)
                        self.last_numlock_press = 0.0
                        return 1  # Suppress NumLock toggle

                    if vk == VK_NUMLOCK:
                        self.last_numlock_press = now

                    # If Layer 2 is already active, a single NumLock press exits Layer 2
                    if self.layer_active and vk == VK_NUMLOCK:
                        self.set_layer_active(False)
                        return 1

                # --- 2. LAYER 2 ACTIVE HANDLING ---
                if self.layer_active:
                    # If this is regular Main Keyboard Enter, NEVER suppress and NEVER mute!
                    if vk == VK_RETURN and not is_extended:
                        return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

                    # On KeyUp for handled keys, suppress to prevent stuck keys
                    if is_keyup:
                        if vk in self.suppressed_vks or (vk == VK_RETURN and is_extended):
                            return 1
                        return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

                    if is_keydown:
                        # Exit Layer 2 on Escape
                        if vk == VK_ESCAPE:
                            print("[Hook] Escape pressed -> Exiting Layer 2")
                            self.set_layer_active(False)
                            return 1

                        # --- Custom Macro Bindings (TKL / Laptop / Custom) ---
                        if mode in ("hybrid", "custom"):
                            if self._matches_binding(custom_bindings.get("volume_up"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                step = self.config.get("volume", {}).get("fine_step_percent", 2) if shift_is_active \
                                    else self.config.get("volume", {}).get("step_percent", 5)
                                self._play_sound("up")
                                if "on_volume_up" in self.callbacks:
                                    self.callbacks["on_volume_up"](step)
                                return 1

                            if self._matches_binding(custom_bindings.get("volume_down"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                step = self.config.get("volume", {}).get("fine_step_percent", 2) if shift_is_active \
                                    else self.config.get("volume", {}).get("step_percent", 5)
                                self._play_sound("down")
                                if "on_volume_down" in self.callbacks:
                                    self.callbacks["on_volume_down"](step)
                                return 1

                            if self._matches_binding(custom_bindings.get("next_app"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                self._play_sound("cycle")
                                if "on_select_next" in self.callbacks:
                                    self.callbacks["on_select_next"]()
                                return 1

                            if self._matches_binding(custom_bindings.get("prev_app"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                self._play_sound("cycle")
                                if "on_select_prev" in self.callbacks:
                                    self.callbacks["on_select_prev"]()
                                return 1

                            if self._matches_binding(custom_bindings.get("toggle_mute"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                self._play_sound("mute")
                                if "on_toggle_mute" in self.callbacks:
                                    self.callbacks["on_toggle_mute"]()
                                return 1

                            if self._matches_binding(custom_bindings.get("exit_layer"), vk, ctrl_is_active, alt_is_active, shift_is_active, win_is_active):
                                print("[Hook] Custom Exit -> Exiting Layer 2")
                                self.set_layer_active(False)
                                return 1

                        # Volume UP (+) on Numpad strictly (VK_ADD = 0x6B)
                        if vk == VK_ADD:
                            step = self.config.get("volume", {}).get("fine_step_percent", 2) if shift_is_active \
                                else self.config.get("volume", {}).get("step_percent", 5)
                            self._play_sound("up")
                            if "on_volume_up" in self.callbacks:
                                self.callbacks["on_volume_up"](step)
                            return 1

                        # Volume DOWN (-) on Numpad strictly (VK_SUBTRACT = 0x6D)
                        if vk == VK_SUBTRACT:
                            step = self.config.get("volume", {}).get("fine_step_percent", 2) if shift_is_active \
                                else self.config.get("volume", {}).get("step_percent", 5)
                            self._play_sound("down")
                            if "on_volume_down" in self.callbacks:
                                self.callbacks["on_volume_down"](step)
                            return 1

                        # Cycle Previous App: 8 (Up), 4 (Left), Divide (/)
                        if vk in (VK_NUMPAD8, VK_NUMPAD4, VK_DIVIDE):
                            self._play_sound("cycle")
                            if "on_select_prev" in self.callbacks:
                                self.callbacks["on_select_prev"]()
                            return 1

                        # Cycle Next App: 2 (Down), 6 (Right), Multiply (*)
                        if vk in (VK_NUMPAD2, VK_NUMPAD6, VK_MULTIPLY):
                            self._play_sound("cycle")
                            if "on_select_next" in self.callbacks:
                                self.callbacks["on_select_next"]()
                            return 1

                        # Mute / Unmute: Numpad 5, or NUMPAD ENTER (VK_RETURN with is_extended == True)
                        if vk == VK_NUMPAD5 or (vk == VK_RETURN and is_extended):
                            self._play_sound("mute")
                            if "on_toggle_mute" in self.callbacks:
                                self.callbacks["on_toggle_mute"]()
                            return 1

                        # Direct App Jump: 0 through 9 on Numpad
                        if VK_NUMPAD0 <= vk <= VK_NUMPAD9:
                            app_index = vk - VK_NUMPAD0
                            self._play_sound("cycle")
                            if "on_select_index" in self.callbacks:
                                self.callbacks["on_select_index"](app_index)
                            return 1

                        # If other numpad keys are pressed, suppress them so they don't type in background
                        if vk in self.suppressed_vks:
                            return 1

            except Exception as e:
                print(f"[Hook] Callback exception: {e}")

            return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

        self._c_callback = HOOKPROC(_hook_proc)
        self.hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._c_callback,
            0,
            0
        )

        if not self.hook_handle:
            print(f"[Hook] Failed to install keyboard hook. Error: {ctypes.GetLastError()}")
            return

        print(f"[Hook] Keyboard hook installed successfully. Layer 2 ready.")

        # Windows Message Pump
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None
        print("[Hook] Keyboard hook loop ended.")
