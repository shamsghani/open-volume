import os
import sys
import shutil
import subprocess
import zipfile

def build():
    print("=" * 60)
    print("  Building Mountain Everest 60 Numpad Audio Layer...")
    print("=" * 60)

    # 1. Clean previous build artifacts
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"Cleaning {folder}/...")
            shutil.rmtree(folder, ignore_errors=True)

    # 2. PyInstaller command
    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "MountainEverestNumpad",
        "--icon", os.path.join("assets", "icon.ico"),
        "--add-data", f"{os.path.join('assets', 'icon.ico')};assets",
        "--add-data", f"{os.path.join('assets', 'icon.png')};assets",
        "--add-data", f"{os.path.join('assets', 'sounds')};assets/sounds",
        "--add-data", f"config.json;.",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "comtypes",
        "--hidden-import", "comtypes.stream",
        "--hidden-import", "comtypes.client",
        "--hidden-import", "pycaw",
        "--hidden-import", "pycaw.pycaw",
        "--hidden-import", "pycaw.constants",
        "--hidden-import", "pycaw.utils",
        "--hidden-import", "PIL._tkinter_finder",
        "main.py"
    ]

    print("\nRunning PyInstaller (onedir)...")
    res = subprocess.run(pyinstaller_args)
    if res.returncode != 0:
        print("[Error] PyInstaller build failed!")
        sys.exit(res.returncode)

    # Copy assets, config.json, README.md, and scripts into dist folder
    dist_dir = os.path.join("dist", "MountainEverestNumpad")
    shutil.copytree("assets", os.path.join(dist_dir, "assets"), dirs_exist_ok=True)
    shutil.copy("config.json", os.path.join(dist_dir, "config.json"))
    shutil.copy("README.md", os.path.join(dist_dir, "README.md"))
    shutil.copy("stop.bat", os.path.join(dist_dir, "stop.bat"))
    shutil.copy("install_startup.bat", os.path.join(dist_dir, "install_startup.bat"))
    shutil.copy("uninstall_startup.bat", os.path.join(dist_dir, "uninstall_startup.bat"))
    shutil.copy("create_desktop_shortcut.bat", os.path.join(dist_dir, "create_desktop_shortcut.bat"))

    # Also build standalone onefile version for portability
    print("\nRunning PyInstaller (onefile standalone)...")
    onefile_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "MountainEverestNumpad_Standalone",
        "--icon", os.path.join("assets", "icon.ico"),
        "--add-data", f"{os.path.join('assets', 'icon.ico')};assets",
        "--add-data", f"{os.path.join('assets', 'icon.png')};assets",
        "--add-data", f"{os.path.join('assets', 'sounds')};assets/sounds",
        "--add-data", f"config.json;.",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "comtypes",
        "--hidden-import", "comtypes.stream",
        "--hidden-import", "comtypes.client",
        "--hidden-import", "pycaw",
        "--hidden-import", "pycaw.pycaw",
        "--hidden-import", "pycaw.constants",
        "--hidden-import", "pycaw.utils",
        "--hidden-import", "PIL._tkinter_finder",
        "main.py"
    ]
    res_onefile = subprocess.run(onefile_args)
    if res_onefile.returncode != 0:
        print("[Warning] Onefile build had issues, continuing with onedir package.")

    # 3. Create release ZIP bundle
    release_dir = os.path.join("dist", "release")
    os.makedirs(release_dir, exist_ok=True)
    zip_path = os.path.join(release_dir, "OpenVolume-v1.3.1-windows-x64.zip")
    compat_zip_path = os.path.join(release_dir, "MountainEverest60-NumpadAudio-v1.3.1-windows-x64.zip")

    print(f"\nPackaging release zip: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(file_path, "dist")
                zipf.write(file_path, rel_path)
        
        # Include the standalone onefile exe in release dir as well
        standalone_exe = os.path.join("dist", "MountainEverestNumpad_Standalone.exe")
        if os.path.exists(standalone_exe):
            zipf.write(standalone_exe, "MountainEverestNumpad_Standalone.exe")

    # Duplicate to legacy name so both download links work
    shutil.copy(zip_path, compat_zip_path)

    print("\n" + "=" * 60)
    print("  BUILD COMPLETE!")
    print(f"  Release Zip: {os.path.abspath(zip_path)}")
    print(f"  Folder Distribution: {os.path.abspath(dist_dir)}")
    print("=" * 60)

if __name__ == "__main__":
    build()
