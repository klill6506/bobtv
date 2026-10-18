# STATUS — BobTV

## Health check 2026-10-18 (Claude, read-only over SSH)
- Box up 19 days; `bobtv-home` and `bobtv-remote` active; home page and Home Assistant answer (200); no service
  errors in 14 days; disk 8% used. Back-key remap and CEC udev rule are installed.
- NordVPN **disconnected with auto-connect DISABLED** (docs said UK auto-connect stays on). UK tiles still
  connect at launch; only boot-time default changed. Ken to decide whether to re-enable.
- Box git checkout: HEAD is the 9/21 commit, but the files on disk match GitHub master (code was copied, not
  pulled) - housekeeping only.
- 354 Arch package updates pending - not applied.

## Open items (from docs/status.md)
- Real doorbell press test (needs a Home Assistant restart to load `rest_command`); Ring live picture.
- Physical remote power-button test (first press from an idle remote only wakes it).
- Roku handoff experiments (`scripts/cec_try.py`, 9/30).
