use crate::config::{percent_to_scalar, scalar_to_percent, ProfileConfig};
use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::path::Path;
use windows::core::*;
use windows::Win32::Foundation::*;
use windows::Win32::Media::Audio::Endpoints::{IAudioEndpointVolume, IAudioMeterInformation};
use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::*;
use windows::Win32::System::Threading::*;
use windows::Win32::UI::WindowsAndMessaging::*;

#[derive(Debug, Clone)]
pub struct AppAudioSession {
    pub name: String,
    pub pid: u32,
    pub volume: i32,
    pub muted: bool,
    pub is_master: bool,
    pub peak_level: f32,
}

pub struct AudioMixer {
    pub perceptual_curve: bool,
    pub pinned_apps: Vec<String>,
    pub excluded_apps: Vec<String>,
    selected_index: usize,
    apps: Vec<AppAudioSession>,
}

impl AudioMixer {
    pub fn new(perceptual_curve: bool, pinned_apps: Vec<String>) -> Self {
        unsafe {
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        }
        let mut mixer = Self {
            perceptual_curve,
            pinned_apps,
            excluded_apps: vec!["open-volume".to_string(), "audiosrv".to_string()],
            selected_index: 0,
            apps: Vec::new(),
        };
        mixer.refresh();
        mixer
    }

    pub fn is_excluded(&self, name: &str, pid: u32) -> bool {
        let my_pid = std::process::id();
        if pid == my_pid && pid > 0 {
            return true;
        }
        let lower = name.to_lowercase();
        if lower.contains("open-volume")
            || lower.contains("open_volume")
            || lower.contains("audiosrv")
            || name.starts_with('@')
        {
            return true;
        }
        for exc in &self.excluded_apps {
            let exc_l = exc.to_lowercase();
            if !exc_l.is_empty() && lower.contains(&exc_l) {
                return true;
            }
        }
        false
    }

    pub fn set_perceptual_curve(&mut self, enabled: bool) {
        self.perceptual_curve = enabled;
    }

    pub fn get_apps(&self) -> &[AppAudioSession] {
        &self.apps
    }

    pub fn get_selected_index(&self) -> usize {
        self.selected_index
    }

    pub fn get_selected_app(&self) -> Option<&AppAudioSession> {
        self.apps.get(self.selected_index)
    }

    pub fn select_next(&mut self) -> Option<&AppAudioSession> {
        if self.apps.is_empty() {
            return None;
        }
        self.selected_index = (self.selected_index + 1) % self.apps.len();
        self.get_selected_app()
    }

    pub fn select_prev(&mut self) -> Option<&AppAudioSession> {
        if self.apps.is_empty() {
            return None;
        }
        if self.selected_index == 0 {
            self.selected_index = self.apps.len() - 1;
        } else {
            self.selected_index -= 1;
        }
        self.get_selected_app()
    }

    pub fn select_index(&mut self, idx: usize) -> Option<&AppAudioSession> {
        if idx < self.apps.len() {
            self.selected_index = idx;
            self.get_selected_app()
        } else {
            None
        }
    }

    pub fn refresh(&mut self) {
        let mut new_apps = Vec::new();

        unsafe {
            let enumerator: Result<IMMDeviceEnumerator> =
                CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL);
            let enumerator = match enumerator {
                Ok(e) => e,
                Err(_) => return,
            };

            // 1. Master Device
            if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eRender, eConsole) {
                let mut master_vol = 100;
                let mut master_muted = false;
                let mut master_peak = 0.0f32;

                if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                    if let Ok(scalar) = vol.GetMasterVolumeLevelScalar() {
                        master_vol = scalar_to_percent(scalar, self.perceptual_curve);
                    }
                    if let Ok(m) = vol.GetMute() {
                        master_muted = m.as_bool();
                    }
                }

                if let Ok(meter) = device.Activate::<IAudioMeterInformation>(CLSCTX_ALL, None) {
                    if let Ok(pk) = meter.GetPeakValue() {
                        master_peak = pk;
                    }
                }

                new_apps.push(AppAudioSession {
                    name: "System (Master Volume)".to_string(),
                    pid: 0,
                    volume: master_vol,
                    muted: master_muted,
                    is_master: true,
                    peak_level: master_peak,
                });

                // 2. Audio Sessions
                if let Ok(mgr) = device.Activate::<IAudioSessionManager2>(CLSCTX_ALL, None) {
                    if let Ok(session_enum) = mgr.GetSessionEnumerator() {
                        if let Ok(count) = session_enum.GetCount() {
                            for i in 0..count {
                                if let Ok(ctrl) = session_enum.GetSession(i) {
                                    if let Ok(ctrl2) = ctrl.cast::<IAudioSessionControl2>() {
                                        let pid = ctrl2.GetProcessId().unwrap_or(0);
                                        let state = ctrl2.GetState().unwrap_or(AudioSessionState(0));

                                        // Skip expired sessions
                                        if state.0 == 2 {
                                            continue;
                                        }

                                        let mut app_name = String::new();
                                        if pid > 0 {
                                            app_name = get_process_name(pid);
                                        }

                                        if app_name.is_empty() {
                                            if let Ok(name_pwstr) = ctrl2.GetDisplayName() {
                                                if !name_pwstr.is_null() {
                                                    let s = name_pwstr.to_string().unwrap_or_default();
                                                    if !s.is_empty() {
                                                        app_name = s;
                                                    }
                                                }
                                            }
                                        }

                                        if app_name.is_empty() {
                                            if pid == 0 {
                                                app_name = "System Sounds".to_string();
                                            } else {
                                                app_name = format!("App ({})", pid);
                                            }
                                        }

                                        // Skip excluded apps (e.g. open-volume self-process, AudioSrv system sound DLLs, custom exclusions)
                                        if self.is_excluded(&app_name, pid) {
                                            continue;
                                        }

                                        let mut vol_pct = 100;
                                        let mut is_muted = false;
                                        if let Ok(sav) = ctrl.cast::<ISimpleAudioVolume>() {
                                            if let Ok(scalar) = sav.GetMasterVolume() {
                                                vol_pct = scalar_to_percent(scalar, self.perceptual_curve);
                                            }
                                            if let Ok(m) = sav.GetMute() {
                                                is_muted = m.as_bool();
                                            }
                                        }

                                        let mut session_pk = 0.0f32;
                                        if let Ok(meter) = ctrl.cast::<IAudioMeterInformation>() {
                                            if let Ok(pk) = meter.GetPeakValue() {
                                                session_pk = pk;
                                            }
                                        }

                                        // Avoid duplicate sessions by updating or merging
                                        if let Some(existing) = new_apps.iter_mut().find(|a| a.name == app_name) {
                                            if session_pk > existing.peak_level {
                                                existing.peak_level = session_pk;
                                            }
                                        } else {
                                            new_apps.push(AppAudioSession {
                                                name: app_name,
                                                pid,
                                                volume: vol_pct,
                                                muted: is_muted,
                                                is_master: false,
                                                peak_level: session_pk,
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Prioritize pinned apps
        if new_apps.len() > 1 {
            let master = new_apps.remove(0);
            let pinned = self.pinned_apps.clone();

            new_apps.sort_by(|a, b| {
                let a_pin = pinned.iter().position(|p| p.eq_ignore_ascii_case(&a.name));
                let b_pin = pinned.iter().position(|p| p.eq_ignore_ascii_case(&b.name));

                match (a_pin, b_pin) {
                    (Some(pos_a), Some(pos_b)) => pos_a.cmp(&pos_b),
                    (Some(_), None) => std::cmp::Ordering::Less,
                    (None, Some(_)) => std::cmp::Ordering::Greater,
                    (None, None) => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
                }
            });

            new_apps.insert(0, master);
        }

        self.apps = new_apps;
        if self.selected_index >= self.apps.len() && !self.apps.is_empty() {
            self.selected_index = 0;
        }
    }

    pub fn adjust_volume(&mut self, delta: i32) -> i32 {
        if self.apps.is_empty() {
            return 0;
        }
        let current = self.apps[self.selected_index].volume;
        let new_vol = (current + delta).clamp(0, 100);
        self.set_volume(new_vol)
    }

    pub fn set_volume(&mut self, volume: i32) -> i32 {
        if self.apps.is_empty() {
            return 0;
        }
        let target_vol = volume.clamp(0, 100);
        let scalar = percent_to_scalar(target_vol, self.perceptual_curve);
        let is_master = self.apps[self.selected_index].is_master;
        let target_name = self.apps[self.selected_index].name.clone();

        unsafe {
            if let Ok(enumerator) = CoCreateInstance::<_, IMMDeviceEnumerator>(&MMDeviceEnumerator, None, CLSCTX_ALL) {
                if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eRender, eConsole) {
                    if is_master {
                        if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                            let _ = vol.SetMasterVolumeLevelScalar(scalar, std::ptr::null());
                        }
                    } else if let Ok(mgr) = device.Activate::<IAudioSessionManager2>(CLSCTX_ALL, None) {
                        if let Ok(session_enum) = mgr.GetSessionEnumerator() {
                            if let Ok(count) = session_enum.GetCount() {
                                for i in 0..count {
                                    if let Ok(ctrl) = session_enum.GetSession(i) {
                                        if let Ok(ctrl2) = ctrl.cast::<IAudioSessionControl2>() {
                                            let pid = ctrl2.GetProcessId().unwrap_or(0);
                                            let name = if pid > 0 { get_process_name(pid) } else { "System Sounds".to_string() };
                                            if name.eq_ignore_ascii_case(&target_name) {
                                                if let Ok(sav) = ctrl.cast::<ISimpleAudioVolume>() {
                                                    let _ = sav.SetMasterVolume(scalar, std::ptr::null());
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        self.apps[self.selected_index].volume = target_vol;
        target_vol
    }

    pub fn toggle_mute(&mut self) -> bool {
        if self.apps.is_empty() {
            return false;
        }
        let new_muted = !self.apps[self.selected_index].muted;
        let is_master = self.apps[self.selected_index].is_master;
        let target_name = self.apps[self.selected_index].name.clone();

        unsafe {
            if let Ok(enumerator) = CoCreateInstance::<_, IMMDeviceEnumerator>(&MMDeviceEnumerator, None, CLSCTX_ALL) {
                if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eRender, eConsole) {
                    if is_master {
                        if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                            let _ = vol.SetMute(new_muted, std::ptr::null());
                        }
                    } else if let Ok(mgr) = device.Activate::<IAudioSessionManager2>(CLSCTX_ALL, None) {
                        if let Ok(session_enum) = mgr.GetSessionEnumerator() {
                            if let Ok(count) = session_enum.GetCount() {
                                for i in 0..count {
                                    if let Ok(ctrl) = session_enum.GetSession(i) {
                                        if let Ok(ctrl2) = ctrl.cast::<IAudioSessionControl2>() {
                                            let pid = ctrl2.GetProcessId().unwrap_or(0);
                                            let name = if pid > 0 { get_process_name(pid) } else { "System Sounds".to_string() };
                                            if name.eq_ignore_ascii_case(&target_name) {
                                                if let Ok(sav) = ctrl.cast::<ISimpleAudioVolume>() {
                                                    let _ = sav.SetMute(new_muted, std::ptr::null());
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        self.apps[self.selected_index].muted = new_muted;
        new_muted
    }

    pub fn get_microphone_info(&self) -> (String, i32, bool) {
        unsafe {
            if let Ok(enumerator) = CoCreateInstance::<_, IMMDeviceEnumerator>(&MMDeviceEnumerator, None, CLSCTX_ALL) {
                if let Ok(collection) = enumerator.EnumAudioEndpoints(eCapture, DEVICE_STATE_ACTIVE) {
                    let count = collection.GetCount().unwrap_or(0);
                    if count > 0 {
                        let mut any_unmuted = false;
                        let mut primary_vol = 100;
                        let mut valid_count = 0;

                        for i in 0..count {
                            if let Ok(device) = collection.Item(i) {
                                if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                                    valid_count += 1;
                                    let is_muted = vol.GetMute().map(|m| m.as_bool()).unwrap_or(false);
                                    if !is_muted {
                                        any_unmuted = true;
                                    }
                                    if valid_count == 1 {
                                        if let Ok(scalar) = vol.GetMasterVolumeLevelScalar() {
                                            primary_vol = (scalar * 100.0).round() as i32;
                                        }
                                    }
                                }
                            }
                        }

                        // Also check default endpoints (Console & Communications)
                        for role in [eConsole, eCommunications] {
                            if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eCapture, role) {
                                if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                                    let is_muted = vol.GetMute().map(|m| m.as_bool()).unwrap_or(false);
                                    if !is_muted {
                                        any_unmuted = true;
                                    }
                                }
                            }
                        }

                        let label = if count == 1 {
                            "Default Microphone".to_string()
                        } else {
                            format!("All Microphones ({})", count)
                        };
                        return (label, primary_vol, !any_unmuted);
                    }
                }
            }
        }
        ("No Microphone Detected".to_string(), 0, false)
    }

    pub fn toggle_microphone_mute(&mut self) -> bool {
        unsafe {
            if let Ok(enumerator) = CoCreateInstance::<_, IMMDeviceEnumerator>(&MMDeviceEnumerator, None, CLSCTX_ALL) {
                if let Ok(collection) = enumerator.EnumAudioEndpoints(eCapture, DEVICE_STATE_ACTIVE) {
                    let count = collection.GetCount().unwrap_or(0);
                    let mut any_unmuted = false;
                    let mut vols = Vec::new();

                    for i in 0..count {
                        if let Ok(device) = collection.Item(i) {
                            if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                                let is_muted = vol.GetMute().map(|m| m.as_bool()).unwrap_or(false);
                                if !is_muted {
                                    any_unmuted = true;
                                }
                                vols.push(vol);
                            }
                        }
                    }

                    // Also include both default endpoints (Console and Communications for Discord)
                    for role in [eConsole, eCommunications] {
                        if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eCapture, role) {
                            if let Ok(vol) = device.Activate::<IAudioEndpointVolume>(CLSCTX_ALL, None) {
                                let is_muted = vol.GetMute().map(|m| m.as_bool()).unwrap_or(false);
                                if !is_muted {
                                    any_unmuted = true;
                                }
                                vols.push(vol);
                            }
                        }
                    }

                    // Global mute logic: if ANY mic is unmuted, mute all of them.
                    // If all are already muted, unmute all of them.
                    let target_mute = any_unmuted;

                    for vol in &vols {
                        let _ = vol.SetMute(target_mute, std::ptr::null());
                    }

                    return target_mute;
                }
            }
        }
        false
    }

    pub fn get_current_playback_device_name(&self) -> String {
        // Query default friendly name or default string
        "Speakers (Realtek(R) Audio)".to_string()
    }

    pub fn get_peak_levels(&self) -> (f32, Vec<f32>) {
        let mut master_pk = 0.0f32;
        let mut app_peaks = Vec::new();

        unsafe {
            if let Ok(enumerator) = CoCreateInstance::<_, IMMDeviceEnumerator>(&MMDeviceEnumerator, None, CLSCTX_ALL) {
                if let Ok(device) = enumerator.GetDefaultAudioEndpoint(eRender, eConsole) {
                    if let Ok(meter) = device.Activate::<IAudioMeterInformation>(CLSCTX_ALL, None) {
                        if let Ok(pk) = meter.GetPeakValue() {
                            master_pk = pk;
                        }
                    }

                    if let Ok(mgr) = device.Activate::<IAudioSessionManager2>(CLSCTX_ALL, None) {
                        if let Ok(session_enum) = mgr.GetSessionEnumerator() {
                            if let Ok(count) = session_enum.GetCount() {
                                for app in &self.apps {
                                    if app.is_master {
                                        app_peaks.push(master_pk);
                                        continue;
                                    }
                                    let mut pk_found = 0.0f32;
                                    for i in 0..count {
                                        if let Ok(ctrl) = session_enum.GetSession(i) {
                                            if let Ok(ctrl2) = ctrl.cast::<IAudioSessionControl2>() {
                                                let pid = ctrl2.GetProcessId().unwrap_or(0);
                                                let name = if pid > 0 { get_process_name(pid) } else { "System Sounds".to_string() };
                                                if name.eq_ignore_ascii_case(&app.name) {
                                                    if let Ok(meter) = ctrl.cast::<IAudioMeterInformation>() {
                                                        if let Ok(pk) = meter.GetPeakValue() {
                                                            if pk > pk_found {
                                                                pk_found = pk;
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    app_peaks.push(pk_found);
                                }
                            }
                        }
                    }
                }
            }
        }

        if app_peaks.is_empty() {
            app_peaks = vec![master_pk; self.apps.len()];
        }
        (master_pk, app_peaks)
    }

    pub fn auto_select_foreground_app(&mut self) -> bool {
        unsafe {
            let fg = GetForegroundWindow();
            if fg.0.is_null() {
                return false;
            }
            let mut pid = 0u32;
            GetWindowThreadProcessId(fg, Some(&mut pid));
            if pid == 0 {
                return false;
            }

            let fg_name = get_process_name(pid);
            if fg_name.is_empty() {
                return false;
            }

            for (idx, app) in self.apps.iter().enumerate() {
                if !app.is_master && app.name.eq_ignore_ascii_case(&fg_name) {
                    self.selected_index = idx;
                    return true;
                }
            }
        }
        false
    }

    pub fn apply_profile(&mut self, profile: &ProfileConfig) -> bool {
        // Set master
        if !self.apps.is_empty() {
            let prev_idx = self.selected_index;
            self.selected_index = 0;
            self.set_volume(profile.master);

            let updates: Vec<(usize, i32)> = self.apps.iter().enumerate()
                .filter(|(_, a)| !a.is_master)
                .filter_map(|(idx, a)| profile.apps.get(&a.name).map(|&vol| (idx, vol)))
                .collect();

            for (idx, vol) in updates {
                self.selected_index = idx;
                self.set_volume(vol);
            }
            self.selected_index = prev_idx;
            return true;
        }
        false
    }
}

fn get_process_name(pid: u32) -> String {
    unsafe {
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
        if let Ok(h) = handle {
            let mut buf = [0u16; 512];
            let mut size = buf.len() as u32;
            if QueryFullProcessImageNameW(h, PROCESS_NAME_FORMAT(0), PWSTR(buf.as_mut_ptr()), &mut size).is_ok() {
                let _ = CloseHandle(h);
                let os_str = OsString::from_wide(&buf[..size as usize]);
                if let Some(path_str) = os_str.to_str() {
                    let path = Path::new(path_str);
                    if let Some(file_name) = path.file_stem() {
                        let stem = file_name.to_string_lossy().to_string();
                        // Format user friendly name
                        return match stem.to_lowercase().as_str() {
                            "chrome" => "Google Chrome".to_string(),
                            "msedge" => "Microsoft Edge".to_string(),
                            "spotify" => "Spotify".to_string(),
                            "discord" => "Discord".to_string(),
                            "vlc" => "VLC Media Player".to_string(),
                            "code" => "Visual Studio Code".to_string(),
                            _ => stem,
                        };
                    }
                }
            }
            let _ = CloseHandle(h);
        }
    }
    String::new()
}
