"""Generate BobTV sonic-logo candidates with ElevenLabs sound generation.

Ken's brief (2026-09-16) is the prompt. Six takes vary the instrument
palette and how literally the model is held to the text; each is saved as
MP3 in audio/elevenlabs/ with the prompt beside it, so the winner can be
reproduced or refined. The key is read from Ken's secrets folder and never
printed.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KEY_FILE = Path(r"D:\dev\Passwords & Secrets\elevenlabs-api-key.txt")
OUT = Path(__file__).resolve().parent / "elevenlabs"
OUT.mkdir(exist_ok=True)
ENDPOINT = "https://api.elevenlabs.io/v1/sound-generation"

# ElevenLabs caps the prompt at 450 characters.
BRIEF = (
    "Premium sonic logo for a streaming TV service. Four sparse ascending notes, "
    "C E G C, warm, not playful: a soft low rounded synth piano note, "
    "then two clean glassy bell-like notes, then a warm final note resolving into a "
    "subtle chord with a very short soft bass under it. A faint warm electronic hum "
    "throughout. Modern, faint retro broadcast feel. No drums, no vocals, no boom. "
    "Spacious, a little reverb, like a sunrise seen from orbit."
)
assert len(BRIEF) <= 440, len(BRIEF)  # the variants add a few characters

TAKES = [
    ("01-brief-literal", BRIEF, 0.75),
    ("02-brief-loose", BRIEF, 0.35),
    (
        "03-felt-piano-and-celesta",
        BRIEF.replace(
            "a soft low rounded synth piano note, then two clean glassy bell-like notes",
            "a soft low felt piano note, then two clean celesta notes",
        ),
        0.6,
    ),
    (
        "04-analog-synth",
        BRIEF.replace(
            "a soft low rounded synth piano note, then two clean glassy bell-like notes",
            "a soft low analog synth pad note, then two clear crystalline synth bell notes",
        ),
        0.6,
    ),
    (
        "05-glass-marimba",
        BRIEF.replace(
            "a soft low rounded synth piano note, then two clean glassy bell-like notes",
            "a soft low mellow electric piano note, then two glass marimba notes",
        ),
        0.6,
    ),
    (
        "06-more-space",
        BRIEF.replace("a little reverb", "a long dark reverb tail"),
        0.55,
    ),
]


def key() -> str:
    try:
        value = KEY_FILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except (OSError, IndexError):
        sys.exit(f"No key at {KEY_FILE}. Save the ElevenLabs API key there, one line.")
    if len(value) < 20:
        sys.exit("The key file does not look like an API key.")
    return value


def generate(api_key: str, text: str, influence: float, seconds: float = 3.5) -> bytes:
    body = json.dumps(
        {"text": text, "duration_seconds": seconds, "prompt_influence": influence}
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    api_key = key()
    for name, text, influence in TAKES:
        target = OUT / f"BobTV-take-{name}.mp3"
        try:
            audio = generate(api_key, text, influence)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            print(f"{name}: HTTP {exc.code} {detail}")
            if exc.code in (401, 403):
                sys.exit("ElevenLabs refused the key.")
            continue
        target.write_bytes(audio)
        (OUT / f"BobTV-take-{name}.txt").write_text(
            f"prompt_influence={influence}\n\n{text}\n", encoding="utf-8"
        )
        print(f"{target.name:44s} {len(audio) // 1024} KB")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
