# BobTV local voice

First milestone: open an existing streaming service and speak a confirmation.
This is command handling, not general AI conversation, show availability lookup,
or episode playback. Both Den Hue lamps give a short flash when the microphone starts listening, including a confirmation question. Hue restores the prior lamp state. The cue runs asynchronously, so unavailable lights do not interrupt voice commands.

## Use

- On BobTV Home, select **Talk to Bob**, or press the MX3 **Mic** button.
- Wait for “What would you like to open?” to finish, then say “Open BBC”,
  “Open Prime”, “Open Hulu”, or “Open YouTube TV”. Other configured services
  have aliases in `voice_control.py`.
- **Hear Bob** plays a greeting without turning on the microphone.
- **Cancel**, Escape on the home screen, or another Mic press on Home stops
  the session. Closing the page alone does not cancel a session; listening
  still ends at its ten-second maximum.
- Ctrl+Alt+B opens BobTV Home and starts/cancels its voice session.
- Outside the BobTV Chromium home window, Mic retains ChatGPT voice behavior.
  Ctrl+Alt+V remains the separate ChatGPT voice shortcut.

The MX3 receiver must be plugged in. Bob uses its XING_WEI microphone explicitly,
not a monitor or another microphone. Replies use PipeWire's current default
output; at work the Dell display may not provide a speaker, so use headphones
or an attached speaker. At home select/test Sony HDMI output.

## Implementation

`voice_control.py` supervises one child process and shares the menu's launch
lock. The child runs `scripts/bob_voice.py` in an isolated Python environment.
Vosk detects the end of a phrase and handles confident service commands;
faster-whisper provides a second local recognition pass for uncertain or
unrecognized phrases, with voice activity detection and confidence checks. Exact allowlisted service
commands call the existing `bobtv.launch` function. If the second recognizer
finds a service but is unsure, Bob asks “Did you mean …?” and requires a
confident spoken yes before launching. Each listening window is capped at ten seconds. Unknown titles, multiple
choices, and negated commands are not mapped to a service.

Marin plays locally cached replies; Piper (en_GB-alan-medium) generates any
uncached replies locally. No microphone recordings
are saved or uploaded. Audio stays in memory, and recognized text stays in the
running menu server until the next session/restart. Temporary reply WAV files
are deleted after playback. The request log contains endpoint names, not speech.
Package/model installation and one-time Marin generation need network access. Launching
services still uses the normal VPN/browser network behavior.

Models and the environment live under `~/.local/share/bobtv/voice/`, outside Git.
`requirements-voice.txt` records the installed packages. The Python 3.12 venv
was created from the Codex bundled runtime; recreate it if that runtime is moved.

Model sources:
- https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
- https://huggingface.co/Systran/faster-whisper-base.en
- https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/alan/medium

Keep the accompanying model cards/licenses with downloaded models. The Alan
voice model card is in the models folder. Piper is GPL-3.0 software.

POST voice endpoints require the same Host, Origin and per-server token checks
as launching tiles. GET status never activates the microphone. Cancellation
terminates the process group, including capture/playback children. A session
watchdog stops it after four minutes, including slow VPN/browser actions.
Cancelling a launch does not undo a VPN change that already completed.

## Marin voice (active)

Ken prefers OpenAI’s Marin voice. BobTV can reuse locally cached Marin WAV files
for all of its current fixed replies, so normal use needs no API connection.
All 40 current replies were generated and validated on September 17, 2026.
The API key was read privately from `~/.config/bobtv/bob.env` (permissions 0600);
the running voice worker does not need to read it.

Run `python3 scripts/setup_marin.py` in your own terminal. It explains the billed
API operation and asks for the key with hidden input; do not paste keys into a
chat. The key is not stored. The exact fixed reply texts are sent to OpenAI,
not microphone audio. Successfully downloaded files are reused if setup is
interrupted. No automatic retry of uncertain/billed requests occurs.

All replies must exist before the `marin/ready` marker activates the new voice.
Future replies absent from the cache use Piper until setup is rerun. Live AI
conversation will need a separate design; this cache only covers fixed replies.

Official API reference: https://developers.openai.com/api/docs/guides/text-to-speech

## Listening light cue

`smart_home.py` posts only to Home Assistant on `127.0.0.1:8123`. The random webhook ID lives in `~/.config/bobtv/smart-home.json` (0600), outside Git. It controls only the short flash automation; no Home Assistant account token is used. The webhook is POST-only and local-only. The Home Assistant automation is named **BobTV — listening cue**; disable it to stop the flashes. `Hear Bob` does not activate the cue.
