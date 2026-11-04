import os
import math
import struct

def ensure_sound_assets(base_dir=None):
    """Ensures warm, round 'bump womp' WAV sound assets exist on disk."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    sounds_dir = os.path.join(base_dir, "assets", "sounds")
    os.makedirs(sounds_dir, exist_ok=True)

    def _generate_womp(filename, start_freq=200, end_freq=100, duration_ms=45, volume=0.55):
        path = os.path.join(sounds_dir, filename)
        if os.path.exists(path) and os.path.getsize(path) > 100:
            return path

        sample_rate = 44100
        n_samples = int(sample_rate * (duration_ms / 1000.0))

        samples = []
        for i in range(n_samples):
            t = i / n_samples
            # Smooth exponential pitch drop
            freq = start_freq * (end_freq / start_freq) ** t
            phase = 2 * math.pi * freq * (i / sample_rate)

            # Round envelope: fast 4ms quadratic attack, smooth exponential decay
            attack_len = int(sample_rate * 0.004)
            if i < attack_len:
                env = (i / attack_len) ** 2
            else:
                decay_t = (i - attack_len) / (n_samples - attack_len)
                env = math.exp(-4.2 * decay_t) * (1.0 - decay_t * 0.5)

            # 85% fundamental + 15% 2nd harmonic for warm, woody 'womp' character
            val = (math.sin(phase) * 0.85 + math.sin(phase * 2) * 0.15) * env * volume
            sample_int = int(max(-32767, min(32767, val * 32767)))
            samples.append(sample_int)

        raw_data = struct.pack(f'<{len(samples)}h', *samples)
        with open(path, 'wb') as f:
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + len(raw_data)))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<IHHIIHH', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
            f.write(b'data')
            f.write(struct.pack('<I', len(raw_data)))
            f.write(raw_data)
        return path

    _generate_womp("womp_up.wav", start_freq=240, end_freq=140, duration_ms=45, volume=0.55)
    _generate_womp("womp_down.wav", start_freq=180, end_freq=95, duration_ms=45, volume=0.55)
    _generate_womp("womp_enter.wav", start_freq=280, end_freq=180, duration_ms=60, volume=0.6)
    _generate_womp("womp_exit.wav", start_freq=160, end_freq=85, duration_ms=45, volume=0.45)
    _generate_womp("womp_mute.wav", start_freq=120, end_freq=60, duration_ms=50, volume=0.5)
    _generate_womp("womp_cycle.wav", start_freq=200, end_freq=120, duration_ms=35, volume=0.45)

    return sounds_dir

import ctypes
from ctypes import wintypes
import winsound

winmm = ctypes.windll.winmm

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ('wFormatTag', wintypes.WORD),
        ('nChannels', wintypes.WORD),
        ('nSamplesPerSec', wintypes.DWORD),
        ('nAvgBytesPerSec', wintypes.DWORD),
        ('nBlockAlign', wintypes.WORD),
        ('wBitsPerSample', wintypes.WORD),
        ('cbSize', wintypes.WORD)
    ]

class WAVEHDR(ctypes.Structure):
    pass
WAVEHDR._fields_ = [
    ('lpData', ctypes.c_char_p),
    ('dwBufferLength', wintypes.DWORD),
    ('dwBytesRecorded', wintypes.DWORD),
    ('dwUser', ctypes.c_void_p),
    ('dwFlags', wintypes.DWORD),
    ('dwLoops', wintypes.DWORD),
    ('lpNext', ctypes.POINTER(WAVEHDR)),
    ('reserved', ctypes.c_void_p)
]

class SoundEngine:
    """High-performance zero-latency polyphonic sound engine.
    
    Uses an 8-voice native WinMM waveOut pool so rapid keypresses or spamming
    overlap naturally into rich audio feedback without cutting out or buffering.
    """
    def __init__(self, sounds_dir, num_voices=8):
        self.sounds_dir = sounds_dir
        self.num_voices = num_voices
        self.voices = []
        self.headers = [None] * num_voices
        self.current_voice = 0
        self.pcm_cache = {}
        self.wav_paths = {}
        self.has_waveout = False

        sound_names = ["up", "down", "enter", "exit", "mute", "cycle"]
        for name in sound_names:
            path = os.path.join(sounds_dir, f"womp_{name}.wav")
            self.wav_paths[name] = path
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                        if len(data) > 44:
                            self.pcm_cache[name] = data[44:]  # Skip 44-byte WAV header
                except Exception:
                    pass

        try:
            wfx = WAVEFORMATEX()
            wfx.wFormatTag = 1   # PCM
            wfx.nChannels = 1    # Mono
            wfx.nSamplesPerSec = 44100
            wfx.wBitsPerSample = 16
            wfx.nBlockAlign = 2
            wfx.nAvgBytesPerSec = 44100 * 2
            wfx.cbSize = 0

            for _ in range(num_voices):
                h = wintypes.HANDLE()
                if winmm.waveOutOpen(ctypes.byref(h), -1, ctypes.byref(wfx), 0, 0, 0) == 0:
                    self.voices.append(h)

            if len(self.voices) > 0:
                self.has_waveout = True
        except Exception:
            self.has_waveout = False

    def play(self, sound_type="cycle"):
        pcm = self.pcm_cache.get(sound_type)
        if self.has_waveout and pcm:
            try:
                idx = self.current_voice
                self.current_voice = (self.current_voice + 1) % len(self.voices)
                h = self.voices[idx]

                old_hdr = self.headers[idx]
                if old_hdr:
                    winmm.waveOutReset(h)
                    winmm.waveOutUnprepareHeader(h, ctypes.byref(old_hdr), ctypes.sizeof(WAVEHDR))

                hdr = WAVEHDR()
                hdr.lpData = pcm
                hdr.dwBufferLength = len(pcm)
                self.headers[idx] = hdr

                winmm.waveOutPrepareHeader(h, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                winmm.waveOutWrite(h, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                return
            except Exception:
                pass

        # Fallback to winsound async playback
        path = self.wav_paths.get(sound_type)
        if path and os.path.exists(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:
                pass

    def close(self):
        for idx, h in enumerate(self.voices):
            try:
                old_hdr = self.headers[idx]
                if old_hdr:
                    winmm.waveOutReset(h)
                    winmm.waveOutUnprepareHeader(h, ctypes.byref(old_hdr), ctypes.sizeof(WAVEHDR))
                winmm.waveOutClose(h)
            except Exception:
                pass
        self.voices.clear()

if __name__ == "__main__":
    p = ensure_sound_assets()
    print(f"Sound assets verified in: {p}")

