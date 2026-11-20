use std::path::PathBuf;
use windows::core::*;
use windows::Win32::Media::Audio::*;

fn get_sound_path(filename: &str) -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let p = dir.join("assets").join("sounds").join(filename);
            if p.exists() {
                return p;
            }
        }
    }
    PathBuf::from("assets").join("sounds").join(filename)
}

pub fn play_layer_on() {
    play_wav("layer_on.wav");
}

pub fn play_layer_off() {
    play_wav("layer_off.wav");
}

pub fn play_volume_tick() {
    play_wav("tick.wav");
}

fn play_wav(filename: &str) {
    let path = get_sound_path(filename);
    if path.exists() {
        if let Some(s) = path.to_str() {
            let hstr = HSTRING::from(s);
            unsafe {
                let _ = PlaySoundW(PCWSTR(hstr.as_ptr()), None, SND_FILENAME | SND_ASYNC);
            }
        }
    }
}
