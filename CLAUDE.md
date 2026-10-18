# CLAUDE.md — BobTV

Full-screen TV home for the MeLE Quieter 4C (Omarchy Linux, host `bobtv`, Tailscale 100.97.9.6) on the
living-room Sony. Python stdlib servers (home 127.0.0.1:8765, phone remote 8766), Chromium kiosk, NordVPN
UK/US switching per tile, HDMI-CEC TV control (Pulse-Eight), MX3 air remote, Home Assistant (Docker) doorbell.

- What it does and how to run it: `README.md`. Full history and handoffs: `docs/status.md`.
- **The live copy runs on the box** at `/home/ken/Documents/ChatGPT/BobTV` (`~/.local/bin/bobtv` points
  there). This PC folder is a clone. SSH: `ssh -i ~/.ssh/bobtv_codex_ed25519 ken@100.97.9.6`.
- Tests: `python3 -m unittest discover -s tests -v` on the box.
- Ask Ken before: changing VPN settings, sudo/system changes, package updates, reboots.
