import ctypes
from ctypes import wintypes
import time
import os

user32 = ctypes.windll.user32
hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
if not user32.SetThreadDesktop(hdesk):
    print("Failed to set thread desktop!")

import tkinter as tk
from PIL import ImageGrab

from config_manager import ConfigManager
from audio_mixer import AudioMixer
from overlay_ui import OverlayWidget

print("Initializing Tk...")
root = tk.Tk()
root.withdraw()

cfg = ConfigManager().config
overlay = OverlayWidget(root, cfg)

mixer = AudioMixer()
apps = mixer.get_apps()
overlay.update_data(apps, 0)
overlay.show()

# Process Tk events
for _ in range(10):
    root.update()
    time.sleep(0.05)

hwnd = overlay._get_toplevel_hwnd()
print("HWND:", hex(hwnd))
print("IsWindowVisible:", user32.IsWindowVisible(hwnd))

rect = (ctypes.c_long * 4)()
user32.GetWindowRect(hwnd, rect)
print(f"Window Rect: [{rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}] (Size: {rect[2]-rect[0]} x {rect[3]-rect[1]})")

# Capture primary screen
save_path = r"C:\Users\shams\.gemini\antigravity\brain\2ad1d299-b721-478a-b192-59cee88770ee\screen_with_widget.png"
im = ImageGrab.grab()
im.save(save_path)
print(f"Screenshot saved to {save_path} ({im.size})")

# Crop the region where the widget should be
crop_box = (max(0, rect[0] - 50), max(0, rect[1] - 50), min(im.size[0], rect[2] + 50), min(im.size[1], rect[3] + 50))
cropped = im.crop(crop_box)
crop_path = r"C:\Users\shams\.gemini\antigravity\brain\2ad1d299-b721-478a-b192-59cee88770ee\widget_crop.png"
cropped.save(crop_path)
print(f"Cropped widget region saved to {crop_path} ({cropped.size})")

root.destroy()

