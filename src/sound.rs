use windows::core::*;
use windows::Win32::Media::Audio::*;

const SOUND_ENTER: &[u8] = include_bytes!("../assets/sounds/womp_enter.wav");
const SOUND_EXIT: &[u8] = include_bytes!("../assets/sounds/womp_exit.wav");
const SOUND_UP: &[u8] = include_bytes!("../assets/sounds/womp_up.wav");
const SOUND_DOWN: &[u8] = include_bytes!("../assets/sounds/womp_down.wav");
const SOUND_CYCLE: &[u8] = include_bytes!("../assets/sounds/womp_cycle.wav");
const SOUND_MUTE: &[u8] = include_bytes!("../assets/sounds/womp_mute.wav");

pub fn play_layer_on() {
    play_memory(SOUND_ENTER);
}

pub fn play_layer_off() {
    play_memory(SOUND_EXIT);
}

pub fn play_volume_up() {
    play_memory(SOUND_UP);
}

pub fn play_volume_down() {
    play_memory(SOUND_DOWN);
}

pub fn play_cycle() {
    play_memory(SOUND_CYCLE);
}

pub fn play_mute() {
    play_memory(SOUND_MUTE);
}

fn play_memory(bytes: &'static [u8]) {
    unsafe {
        let _ = PlaySoundW(
            PCWSTR(bytes.as_ptr() as *const u16),
            None,
            SND_MEMORY | SND_ASYNC | SND_NODEFAULT,
        );
    }
}
