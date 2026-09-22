# BobTV

A local, full-screen entertainment home for the MeLE running Omarchy.

## Use

- `bobtv home`: starts the loopback server if needed and opens the home screen, or focuses the existing home window.
- `Ctrl+Alt+H`: return to BobTV from any app (installed desktop shortcut).
- MX3 remote **Mic** button: talks to Bob on the BobTV home screen; otherwise toggles ChatGPT voice.
- **Talk to Bob** / **Hear Bob** on Home: local voice commands and a spoken greeting. **Ctrl+Alt+B** starts/cancels BobTV voice. See [voice setup](docs/voice.md).
- MX3 remote **Home** button: return to BobTV (installed desktop shortcut).
- `Alt+Tab`: switch between open apps; arrow keys and Enter navigate BobTV.
- `bobtv list`: lists configured services.
- `bobtv launch SERVICE`: verifies the connection and opens the service in Chromium.
- `bobtv launch SERVICE --check-only`: verifies the connection without opening a browser.

UK tiles connect NordVPN to the UK. US tiles disconnect NordVPN and verify its
reported disconnected state before opening. US mode uses the machine's actual
home connection; it does not spoof or verify US geography. A router VPN, proxy,
location permissions, DRM support, sign-in, and subscriptions can still affect
playback. Switching affects the entire computer and any other open streams.
UK auto-connect at boot stays enabled; selecting a US tile does not change that
setting. VPN state is checked at launch, not enforced throughout playback.

The home screen uses its own Chromium profile; streaming sites use the existing
Chromium profile to preserve sign-ins. Arrow keys and Tab move focus; Enter opens
a service. The home screen uses kiosk mode; Alt+F4 closes a window. Close a streaming
window to return to the home screen. The local server starts with the desktop session; opening the full-screen browser remains on demand.

## Implementation

This workspace is now the maintained implementation. The original
`/home/ken/Projects/bobtv` directory remains as a pre-home-screen copy.
`~/.local/bin/bobtv` points here. Services and connection policies are in
`services.json`. Every interface uses `bobtv.py` actions.

The Python standard-library HTTP server binds only to 127.0.0.1:8765. Launches
require a same-origin POST and a per-process token, allow only configured service
IDs, and share the command layer's action lock. No shell interpolation is used
for service input. The server exposes the home-page files, five explicitly allowlisted branding
assets, and explicit API routes. It is a local appliance interface, not an internet-facing service.

Logs: `~/.local/state/bobtv/home.log` and `browser.log`.
Run tests: `python3 -m unittest discover -s tests -v` (loopback sockets required).

See [the original recap](docs/project-recap-2026-09-16.txt) and
[project status](docs/status.md) for the broader plan.

## Server service

The installed `bobtv-home.service` user unit starts at graphical login and restarts
on failure. The home launcher starts that service if needed. Inspect it with
`systemctl --user status bobtv-home.service`; logs are available with
`journalctl --user -u bobtv-home.service`. The unit source is in `systemd/`.

## Shared branding

Upload artwork and audio to [assets/branding](assets/branding/README.md).
Use [artwork](assets/branding/artwork/), [sound](assets/branding/sound/), or
[concepts](assets/branding/concepts/) for alternatives. Files are reviewed before
being used in the live interface. Project decisions and handoffs live in
[docs/status.md](docs/status.md).

## Sunrise theme and intro

The supplied 4K Earth background and transparent BobTV logo theme the sidebar
and three-column home screen. The approved splash fades in with the WAV sound
master over 6.3 seconds with the six-second extended sound, once per tab session. Refreshing or returning
from a streaming window does not replay it. Preview intro replays it on demand;
Skip or Escape stops audio and restores focus. Browser autoplay restrictions
can make the initial intro silent; click Preview intro to hear it. Reduced-motion
preferences disable the image fade. The artwork originals remain unchanged.

## iPhone button remote

A separate paired LAN remote runs on port 8766. See [phone setup](docs/phone-remote.md). The home server on port 8765 defaults to loopback-only.

For a separate Tailscale home-screen listener, use `bobtv serve --host 0.0.0.0`
and set `BOBTV_PASSWORD`. Non-loopback listeners refuse to start without it.
Tailscale IPs are allowed automatically; set `BOBTV_ALLOWED_HOSTS` to a
comma-separated list for DNS names. Voice controls and VPN release remain
local-only.
