"""Master the chosen ElevenLabs take: decode, lift it to -1 dBFS (it came
in at -14.6, far too quiet next to programme audio), lead with 0.35 s of
silence so the picture can start from black, and write a lossless WAV
master beside the MP3."""
import wave
from pathlib import Path

import miniaudio
import numpy as np

src = Path(r"D:\Personal\bob-tv\brand\audio\BobTV-signature.mp3")
dst = src.with_name("BobTV-signature-master.wav")
LEAD_IN = 0.35

decoded = miniaudio.decode_file(str(src), output_format=miniaudio.SampleFormat.SIGNED16, nchannels=2)
rate = decoded.sample_rate
x = np.frombuffer(decoded.samples, dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768.0
gain = (10 ** (-1.0 / 20)) / (np.max(np.abs(x)) + 1e-9)
x = x * gain
lead = np.zeros((int(rate * LEAD_IN), 2))
out = np.vstack([lead, x])
with wave.open(str(dst), "wb") as handle:
    handle.setnchannels(2)
    handle.setsampwidth(2)
    handle.setframerate(rate)
    handle.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
print(f"{dst.name}: {len(out) / rate:.2f}s, gain +{20 * np.log10(gain):.1f} dB, lead-in {LEAD_IN}s")
