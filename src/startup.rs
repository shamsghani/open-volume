use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;
use windows::core::*;
use windows::Win32::System::Com::*;
use windows::Win32::UI::Shell::*;
use windows::Win32::UI::WindowsAndMessaging::*;

const TASK_NAME: &str = "OpenVolume";
const CREATE_NO_WINDOW: u32 = 0x08000000;

pub fn is_admin() -> bool {
    unsafe { windows::Win32::UI::Shell::IsUserAnAdmin().as_bool() }
}

pub fn ensure_admin_elevation() {
    if std::env::args().any(|a| a == "--no-elevate") {
        return;
    }

    if !is_admin() {
        if let Ok(exe) = std::env::current_exe() {
            let exe_str = exe.to_str().unwrap_or_default();
            let h_exe = HSTRING::from(exe_str);
            let dir_str = exe.parent().and_then(|p| p.to_str()).unwrap_or_default();
            let h_dir = HSTRING::from(dir_str);

            let args: Vec<String> = std::env::args().skip(1).collect();
            let args_joined = args.join(" ");
            let h_args = HSTRING::from(args_joined.as_str());

            unsafe {
                let ret = ShellExecuteW(
                    None,
                    w!("runas"),
                    PCWSTR(h_exe.as_ptr()),
                    PCWSTR(h_args.as_ptr()),
                    PCWSTR(h_dir.as_ptr()),
                    SW_HIDE,
                );
                if (ret.0 as usize) > 32 {
                    std::process::exit(0);
                }
            }
        }
    }
}

pub fn is_startup_enabled() -> bool {
    let output = Command::new("schtasks")
        .args(["/query", "/tn", TASK_NAME])
        .creation_flags(CREATE_NO_WINDOW)
        .output();

    if let Ok(out) = output {
        if out.status.success() {
            let text = String::from_utf8_lossy(&out.stdout);
            return text.contains(TASK_NAME);
        }
    }
    false
}

pub fn set_startup_enabled(enable: bool) -> bool {
    if !enable {
        let output = Command::new("schtasks")
            .args(["/delete", "/tn", TASK_NAME, "/f"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        return output.map(|o| o.status.success()).unwrap_or(false);
    }

    if let Ok(exe) = std::env::current_exe() {
        let tr_target = format!("\"{}\"", exe.display());
        let output = Command::new("schtasks")
            .args([
                "/create",
                "/tn",
                TASK_NAME,
                "/tr",
                &tr_target,
                "/sc",
                "onlogon",
                "/rl",
                "highest",
                "/f",
            ])
            .creation_flags(CREATE_NO_WINDOW)
            .output();

        if let Ok(out) = output {
            return out.status.success();
        }
    }
    false
}

pub fn get_desktop_dir() -> PathBuf {
    if let Ok(userprofile) = std::env::var("USERPROFILE") {
        let onedrive = PathBuf::from(&userprofile).join("OneDrive").join("Desktop");
        if onedrive.is_dir() {
            return onedrive;
        }
        let std_desktop = PathBuf::from(&userprofile).join("Desktop");
        if std_desktop.is_dir() {
            return std_desktop;
        }
    }
    PathBuf::from(r"C:\Users\Default\Desktop")
}

pub fn get_desktop_shortcut_path() -> PathBuf {
    get_desktop_dir().join("Open Volume.lnk")
}

pub fn is_desktop_shortcut_exists() -> bool {
    get_desktop_shortcut_path().exists()
}

pub fn create_desktop_shortcut() -> bool {
    let dest_path = get_desktop_shortcut_path();
    let exe_path = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return false,
    };

    unsafe {
        let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);

        let shell_link: Result<IShellLinkW> = CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER);
        if let Ok(link) = shell_link {
            let h_exe = HSTRING::from(exe_path.to_str().unwrap_or_default());
            let _ = link.SetPath(PCWSTR(h_exe.as_ptr()));
            let _ = link.SetDescription(w!("Open-Volume Audio Mixer & Macropad"));

            if let Some(parent) = exe_path.parent() {
                let h_dir = HSTRING::from(parent.to_str().unwrap_or_default());
                let _ = link.SetWorkingDirectory(PCWSTR(h_dir.as_ptr()));
                let ico = parent.join("assets").join("icon.ico");
                if ico.exists() {
                    let h_ico = HSTRING::from(ico.to_str().unwrap_or_default());
                    let _ = link.SetIconLocation(PCWSTR(h_ico.as_ptr()), 0);
                }
            }

            if let Ok(persist) = link.cast::<IPersistFile>() {
                let h_dest = HSTRING::from(dest_path.to_str().unwrap_or_default());
                return persist.Save(PCWSTR(h_dest.as_ptr()), true).is_ok();
            }
        }
    }
    false
}
