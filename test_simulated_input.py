import subprocess
import time
import ctypes
from ctypes import wintypes
import sys
import os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def attach_default():
    hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        user32.SetThreadDesktop(hdesk)

# Key constants
VK_CONTROL = 0x11
VK_NUMLOCK = 0x90
VK_ADD = 0x6B
VK_NUMPAD2 = 0x62
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

def press_key(vk, extended=False):
    flags = KEYEVENTF_EXTENDEDKEY if extended else 0
    user32.keybd_event(vk, 0, flags, 0)

def release_key(vk, extended=False):
    flags = (KEYEVENTF_EXTENDEDKEY if extended else 0) | KEYEVENTF_KEYUP
    user32.keybd_event(vk, 0, flags, 0)

def tap_key(vk, extended=False):
    press_key(vk, extended)
    time.sleep(0.05)
    release_key(vk, extended)

def test_simulation():
    attach_default()
    print("[Simulator] Launching main.py...")
    p = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(1.5)  # Wait for hook to install

    print("\n--- STEP 1: Simulating Ctrl + NumLock ---")
    press_key(VK_CONTROL)
    time.sleep(0.05)
    tap_key(VK_NUMLOCK, extended=True)
    time.sleep(0.05)
    release_key(VK_CONTROL)

    time.sleep(1.0)

    print("\n--- STEP 2: Simulating Numpad + (Volume Up) ---")
    tap_key(VK_ADD)
    time.sleep(0.5)

    print("\n--- STEP 3: Simulating Numpad 2 (Cycle Next App) ---")
    tap_key(VK_NUMPAD2)
    time.sleep(0.5)

    print("\n--- STEP 4: Simulating NumLock (Exit Layer 2) ---")
    tap_key(VK_NUMLOCK, extended=True)
    time.sleep(1.0)

    p.terminate()
    stdout, stderr = p.communicate(timeout=3.0)

    print("\n--- PROCESS OUTPUT ---")
    print(stdout)
    if stderr:
        print("[STDERR]:", stderr)

    # Assertions
    assert "Trigger detected" in stdout, "Failed to detect Ctrl+NumLock trigger!"
    assert "Layer 2 state changed -> ACTIVE" in stdout, "Layer 2 was not activated!"
    assert "Layer 2 state changed -> INACTIVE" in stdout, "Layer 2 was not deactivated!"
    print("\n[SUCCESS] Simulated input test passed completely!")

if __name__ == "__main__":
    test_simulation()

