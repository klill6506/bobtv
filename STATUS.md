# STATUS — BobTV

## Health check 2026-10-18 (Claude, read-only over SSH)
- Box up 19 days; `bobtv-home` and `bobtv-remote` active; home page and Home Assistant answer (200); no service
  errors in 14 days; disk 8% used. Back-key remap and CEC udev rule are installed.
- NordVPN **disconnected with auto-connect DISABLED** (docs said UK auto-connect stays on). UK tiles still
  connect at launch; only boot-time default changed. **Leave it OFF (Ken, 10/18): the VPN disconnects Tailscale.**
- Box git checkout: HEAD is the 9/21 commit, but the files on disk match GitHub master (code was copied, not
  pulled) - housekeeping only.
- 354 Arch package updates pending - not applied.

## Open items (from docs/status.md)
- Real doorbell press test (needs a Home Assistant restart to load `rest_command`); Ring live picture.
- Physical remote power-button test (first press from an idle remote only wakes it).
- Roku handoff experiments (`scripts/cec_try.py`, 9/30).

## Update run 2026-10-18
- Ken running `omarchy-update` in tmux session `update` (Omarchy snapshots first). Watch: libcec 7.1.1 -> 8.1.7 (major; rollback pkg in /var/cache/pacman/pkg), tailscale 1.104, kernel 7.2.8 + systemd 262 (reboot needs the LUKS passphrase at the box). CEC baseline before update: `pow 0.0.0.0` -> on.
- RESULT: third try succeeded (1st: OMARCHY_PATH unset under tmux - use `env OMARCHY_PATH=/usr/share/omarchy omarchy-update`; 2nd: chatgpt-bin download stalled). Ken rebooted 15:38. Now kernel 7.2.8, libcec 8.1.7 (CEC `pow` works), tailscale 1.104, 0 updates pending. Services, HA (2026.9.2) and home page OK.
- Ring push listener crashed on HA start (`firebase_messaging ... Incorrect padding, shutting down FcmPushClient`) - ding events likely won't arrive. Next: Ken reloads the Ring integration, then a real doorbell press.
- Harmless boot noise: systemd 262 TPM NvPCR units fail (no TPM use); sshd failed once at boot then started.
