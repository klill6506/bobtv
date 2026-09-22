"""Make the six-second sunrise variant from the original lossless master.

Requires ffmpeg with the Rubber Band filter. Keeps pitch and the 0.35s lead-in.
"""
from pathlib import Path
import subprocess
import wave

root = Path(__file__).resolve().parent.parent
source = root / 'bobtv-startup-sunrise-v1.wav'
target = root / 'bobtv-startup-sunrise-v2-long.wav'
with wave.open(str(source)) as audio:
    duration = audio.getnframes() / audio.getframerate()
tempo = (duration - 0.35) / (6.0 - 0.35)
subprocess.run([
    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
    '-af', f'atrim=start=0.35,asetpts=PTS-STARTPTS,rubberband=tempo={tempo}:pitch=1,'
           'asetpts=N/SR/TB,adelay=350:all=1,apad=whole_dur=6,atrim=end_sample=264600,afade=t=out:st=5.5:d=0.5',
    '-ar', '44100', '-ac', '2', '-c:a', 'pcm_s16le', str(target),
], check=True)
print(target)
