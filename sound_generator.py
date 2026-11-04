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

if __name__ == "__main__":
    p = ensure_sound_assets()
    print(f"Sound assets verified in: {p}")

