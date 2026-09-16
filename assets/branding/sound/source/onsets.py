"""Where do the notes land in the chosen take? Decode the MP3, follow the
loudness envelope, and report the moments it jumps -- the animation's cue
sheet. Also report length and where the sound is effectively over."""
import sys

import miniaudio
import numpy as np

path = sys.argv[1]
decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1)
rate = decoded.sample_rate
x = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float64) / 32768.0
length = len(x) / rate

# Loudness envelope in 10 ms hops.
hop = int(rate * 0.010)
frames = len(x) // hop
env = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(frames)])
db = 20 * np.log10(env + 1e-6)
peak_db = db.max()

# Spectral flux: how much the spectrum changes hop to hop -- a new note
# shows as a jump even if loudness barely moves.
win = int(rate * 0.046)
spec_prev = None
flux = np.zeros(frames)
for i in range(frames):
    seg = x[i * hop:i * hop + win]
    if len(seg) < win:
        break
    spec = np.abs(np.fft.rfft(seg * np.hanning(win)))
    if spec_prev is not None:
        flux[i] = np.sum(np.clip(spec - spec_prev, 0, None))
    spec_prev = spec
flux /= flux.max() + 1e-9

# Onsets: flux peaks above a threshold, at least 180 ms apart.
threshold = 0.22
onsets = []
last = -1.0
for i in range(1, frames - 1):
    t = i * hop / rate
    if flux[i] > threshold and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and t - last > 0.18:
        onsets.append((t, flux[i], db[i]))
        last = t

print(f"length {length:.2f}s  sample rate {rate}  peak {peak_db:.1f} dBFS")
print("first audible (> peak-40dB):", f"{next((i for i in range(frames) if db[i] > peak_db - 40), 0) * hop / rate:.2f}s")
tail = next((i for i in range(frames - 1, 0, -1) if db[i] > peak_db - 30), frames) * hop / rate
print(f"effectively over (< peak-30dB): {tail:.2f}s")
print("onsets (time, flux, level):")
for t, f, level in onsets:
    print(f"   {t:5.2f}s  flux {f:.2f}  {level:6.1f} dB")
