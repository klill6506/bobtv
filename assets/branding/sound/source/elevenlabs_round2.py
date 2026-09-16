"""Round two: Ken picked take 04 (analog synth) as closest. Six nudges around
that palette, saved as BobTV-r2-*.mp3 with their prompts beside them."""
import sys
import time
import urllib.error

from elevenlabs_takes import OUT, generate, key

BASE = (
    "Premium sonic logo for a streaming TV service. Exactly four sparse ascending notes, "
    "C E G C, warm, not playful: a soft low analog synth pad note, then two clear "
    "crystalline synth bell notes, then a warm final note resolving into a subtle chord "
    "with a very short soft bass under it. A faint warm electronic hum throughout. "
    "Modern, faint retro broadcast feel. No drums, no vocals, no boom. Spacious, a "
    "little reverb, like a sunrise seen from orbit."
)

TAKES = [
    ("01-tight", BASE, 0.85),
    ("02-loose", BASE, 0.4),
    (
        "03-separate-notes",
        BASE.replace("Exactly four sparse ascending notes, C E G C, warm, not playful:",
                     "Four slow, separate ascending notes, C E G C, each ringing alone:"),
        0.7,
    ),
    (
        "04-smaller-ending",
        BASE.replace("a warm final note resolving into a subtle chord with a very short soft bass under it",
                     "a warm final note that gently resolves, with only a hint of soft low bass"),
        0.65,
    ),
    (
        "05-drier",
        BASE.replace("Spacious, a little reverb, like a sunrise seen from orbit.",
                     "Clean and close, very little reverb, intimate."),
        0.65,
    ),
    (
        "06-starlight",
        BASE.replace("Spacious, a little reverb, like a sunrise seen from orbit.",
                     "Spacious, a little reverb, a starlight shimmer at the end."),
        0.65,
    ),
]

for name, text, _ in TAKES:
    assert len(text) <= 450, (name, len(text))


def main() -> None:
    api_key = key()
    for name, text, influence in TAKES:
        target = OUT / f"BobTV-r2-{name}.mp3"
        try:
            audio = generate(api_key, text, influence)
        except urllib.error.HTTPError as exc:
            print(f"{name}: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')[:200]}")
            if exc.code in (401, 403):
                sys.exit("ElevenLabs refused the key.")
            continue
        target.write_bytes(audio)
        (OUT / f"BobTV-r2-{name}.txt").write_text(f"prompt_influence={influence}\n\n{text}\n", encoding="utf-8")
        print(f"{target.name:36s} {len(audio) // 1024} KB")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
