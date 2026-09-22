# Sound

BobTV's startup sound — the sonic logo — and the takes it was chosen from.
Naming and handoff rules are in [branding handoff](../README.md).

## Longer splash version — September 17

`bobtv-startup-sunrise-v2-long.wav` is the active six-second variant.
Derived locally from the original WAV using FFmpeg Rubber Band pitch-preserving
stretching, keeping the four-note motif, stereo, and 0.35-second silent lead-in.
A final half-second fade softens the ending. The splash now lasts 6.3 seconds.
Regenerate with `python3 assets/branding/sound/source/extend_take.py`.
The original master and generated takes remain available. Listening approval
of this slower variant is still pending.

## The chosen sound: `bobtv-startup-sunrise-v1`

| File | What |
|---|---|
| `bobtv-startup-sunrise-v1.wav` | **The master — build against this.** 0.35 s of silence in front so the picture opens from black, peak −1 dBFS. 3.83 s, 44.1 kHz, 16‑bit stereo. |
| `bobtv-startup-sunrise-v1.mp3` | The take exactly as generated (3.48 s). Playback preview / reference. |
| `bobtv-startup-sunrise-v1.prompt.txt` | The exact text prompt and settings that produced it. |

**Creator / source:** ElevenLabs sound generation (`/v1/sound-generation`),
run 2026‑09‑16 from Ken's written brief under Ken's ElevenLabs account.
Round 2, take 01 of twelve; Ken's pick. **Usage rights:** generated output on
Ken's paid ElevenLabs plan — check the plan's commercial terms before any
use outside BobTV. **Pairs with:** the "Signature" splash concept — the sun
cresting the night side of Earth, the BobTV wordmark above it (see
`../concepts/` once that artwork lands). **Intended use:** plays once at app
launch, under the splash. Never on every screen.

### The brief that made it

> Premium sonic logo for a streaming TV service. Exactly four sparse
> ascending notes, C E G C, warm, not playful: a soft low analog synth pad
> note, then two clear crystalline synth bell notes, then a warm final note
> resolving into a subtle chord with a very short soft bass under it. A faint
> warm electronic hum throughout. Modern, faint retro broadcast feel. No
> drums, no vocals, no boom. Spacious, a little reverb, like a sunrise seen
> from orbit.

Prompt influence 0.85.

### Cue sheet — time the picture to the sound

The take plays its four notes fast, inside the first second, then lets the
chord ring. That is how the strongest idents behave (Netflix's is half a
second of notes and a long tail), so the splash animation should follow the
audio. Onsets measured in the **master** with `source/onsets.py`:

| Time | Sound | Picture |
|---|---|---|
| 0.00 s | silence | black |
| **0.36 s** | note 1 — low pad, the hum begins | the rim of Earth appears |
| **0.59 s** | note 2 — first bell | city lights twinkle on |
| **0.80 s** | note 3 — second bell | sunrise breaks over the horizon |
| **1.00 s** | note 4 — the resolve, bass under it | BobTV lettering fades in |
| **1.21 s** | the chord blooms | the flare through the "o" in Bob |
| ~2.6 s | sound effectively over (−30 dB) | wordmark settled, tagline in |
| 3.2–3.5 s | silence | home screen |

Everything after 1.21 s is tail: use it for the wordmark to settle and the
tagline to appear.

## `alternates/` — the other eleven takes

Round 1 (`r1-*`) varied the instrument palette from the same brief: literal,
loose, felt piano + celesta, analog synth, glass marimba, more space. Ken
picked `r1-04-analog-synth` as closest. Round 2 (`r2-*`) made six nudges
around that palette; `r2-01-tight` won and became `v1`. Each `.mp3` has its
prompt in the `.txt` beside it. Kept so a sibling (a bumper, a seasonal
variant) can be generated from the same words — **do not write a new
motif; the four notes are the brand.**

## `source/` — how to reproduce or extend

- `elevenlabs_takes.py`, `elevenlabs_round2.py` — the generators. They read
  the API key from a file outside the repo (Ken's secrets folder on his
  PC); point `KEY_FILE` somewhere else on another machine. Prompts are
  capped at 450 characters by the API.
- `master_take.py` — decodes the chosen MP3, adds the lead‑in, normalises
  to −1 dBFS, writes the WAV master. Needs `miniaudio` and `numpy`.
- `onsets.py` — measures where the notes land in any take, for the cue
  sheet. Re‑run it if the master is ever re‑cut.

Paths inside these scripts are Ken's Windows paths; adjust before running
elsewhere.

## Rules of use

- The full sting plays **once**, at launch.
- A shorter bumper, if wanted, is cut from `v1` (first ~1.5 s with a fade)
  or generated from the same prompt — never a new tune.
- The WAV is the source of truth; encode AAC/MP3/OGG for the app from it.
