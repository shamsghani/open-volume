#![allow(unused_must_use, dead_code, static_mut_refs, unused_assignments)]

pub mod audio;
pub mod config;
pub mod hook;
pub mod overlay;
pub mod settings;
pub mod sound;
pub mod startup;
pub mod tray;

pub fn log_event(msg: &str) {
    let log_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("open_volume.log")))
        .unwrap_or_else(|| std::path::PathBuf::from("open_volume.log"));
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(log_path) {
        use std::io::Write;
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let _ = writeln!(f, "[{}] {}", ts, msg);
    }
}
