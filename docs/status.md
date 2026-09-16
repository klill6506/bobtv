# BobTV handoff — 2026-09-16

## Confirmed in this task

- This Codex session runs on host `bobtv` as part of the BobTV project.
- Original source was at `/home/ken/Projects/bobtv`, including `bobtv.py`,
  `services.json`, `README.md`, and tests.
- `/home/ken/.local/bin/bobtv` now invokes the maintained source in this workspace.
- Prior Codex task **Log into NordVPN** is readable directly from this task.
  Task ID: `01a0ab2b-69e3-7d62-abaf-0dee3fef06b8`.
- That task successfully executed `nordvpn set autoconnect on United_Kingdom`
  and reported that the kill switch remained disabled. Its final turn was
  interrupted before a completed reboot test was recorded.
- Verified live daemon access outside the sandbox: connected to United Kingdom,
  auto-connect enabled, kill switch disabled, and nordvpnd enabled at boot.
- Reapplied UK-specific auto-connect successfully.
- All three installed service commands passed `--check-only` against the live UK
  VPN. These checks do not open Chromium or verify website playback.
- All seven existing Python unit tests passed.
- With Ken's explicit approval, enabled persistent Omarchy Stay Awake using
  `omarchy toggle idle stay-awake`. Runtime IPC confirmed `enabled: false`,
  `stayAwake: true`, and no screensaver or lock timers running. The persistent
  marker exists at `/home/ken/.local/state/omarchy/indicators/stay-awake`.
- Desktop auto-login configuration confirms user ken and omarchy.desktop.
- Ken approved reboot after the checks. Pre-reboot boot ID:
  `f4f17ebf-3df7-4472-923e-a00af0f63e59`. Post-reboot verification completed below.

## Reported by the supplied recap; not retested here

- BBC playback works; BBC, ITVX, and Channel 4 actions exist.
- Desktop auto-login works; disk encryption remains enabled.
- Appliance-friendly idle behavior is now configured and verified in-session.
- Air-mouse remote and Pulse-Eight USB-CEC adapter are ordered.
- Home screen, Home Assistant, profiles, and What'sOn/Trakt integration are planned.

## Post-reboot verification — completed 2026-09-16

- New boot ID: `117940f9-9de2-46ed-8630-ee85fd5687ac`.
- SDDM boot log confirms `sddm-autologin` opened ken's desktop session.
- Before running any BobTV action, NordVPN was connected to United Kingdom;
  auto-connect remained enabled and kill switch disabled. Daemon was active.
- Omarchy runtime reports Stay Awake true, idle handling disabled, and no lock or
  screensaver timers running after reboot.
- BBC, ITVX, and Channel 4 all passed live `--check-only` checks after reboot.
- Actual BBC browser-launch command succeeded. Website playback was not retested.
- SDDM reports the login keyring could not unlock automatically; the BBC launch
  command nevertheless succeeded. Watch for browser credential prompts in use.
- Disk-encryption configuration was not changed.

## Next implementation milestone

1. When the remote arrives, identify its input events and map buttons to BobTV.
2. Add CEC when the adapter arrives, then the home screen and home integration.

## Design constraints

- All interfaces invoke the same BobTV action layer.
- Services and countries belong in configuration.
- Preserve encryption and existing working entertainment systems.
- Support three people and a household profile in future design.
- Use Home Assistant for device integration; reuse What'sOn and Trakt.
- Favor accessible, assembled hardware over fiddly soldering.
- Keep implementation incremental and record verified state separately from plans.

## Reversing Stay Awake

`omarchy toggle idle allow-idle` restores the existing 900-second screensaver
and 1800-second automatic lock settings. Manual locking remains available while
Stay Awake is enabled. No disk-encryption settings were changed.

## Coordination

Use this project as the main planning and implementation conversation. Available
Codex task tools can inspect prior tasks and send follow-up work when requested;
Ken need not manually relay messages through ChatGPT. No second task needs to run
just to work on this machine, since this session already has local access.

## Home screen — 2026-09-16

- Maintained Python source, catalog, tests, and local web UI now live in this
  project. The original Projects/bobtv directory is preserved as a legacy copy.
- Launcher backup: `~/.local/bin/bobtv.before-home-screen`.
- `bobtv home` opens a dedicated Chromium kiosk browser. Desktop inspection
  verified a full-screen home window (1536×864). Initial app mode did not honor
  the full-screen flag, so kiosk mode is used instead.
- BobTV is available in the application menu. Startup remains on demand.
- UK tiles: BBC, ITVX, Channel 4. US/home-internet tiles: Prime Video, YouTube TV,
  YouTube, HBO Max, Hulu. US actions disconnect and verify NordVPN first.
- Live US-disconnect → UK-reconnect check passed; UK connection restored.
- Browser-rendered layout and arrow-key focus checked. BBC tile successfully
  launched the existing streaming browser through the local API.
- Playback/subscription/DRM compatibility for newly added services is unverified.
- Home server binds loopback only; same-origin/token checks protect launch POSTs.
- Remote mapping and CEC remain the next hardware-dependent tasks.

## Branded tiles

- Replaced plain-text service marks with eight locally bundled SVG logos and
  recognizable service colors. Sources are recorded in web/brands/sources.json.
- Verified eight rendered marks and no horizontal overflow at 1536×864; JavaScript
  syntax check passed. VPN and launch behavior unchanged.
- Regenerate embedded logos with `python3 scripts/build_brand_logos.py`.
- Ken has a Trakt API integration for show artwork; future Continue Watching
  design should investigate that existing integration rather than duplicate it.

## Home availability fix

- The temporary development server stopped, leaving port 8765 without a listener.
- Installed and enabled the user unit bobtv-home.service for graphical-session.target,
  with Restart=on-failure. Server is independent of the Codex task lifecycle.
- Updated `bobtv home` to start the installed service if unavailable.
- Verified HTTP page/status responses and opened a working browser tab.
- What’sOn repository inspection awaits its URL; local gh is not authenticated.

## Continue Watching and expanded catalog

- Ken explicitly approved read-only live What’sOn show/progress/poster access.
- Added Apple TV, Paramount+, Peacock to US VPN-off services with bundled logos.
- Landing page now displays active, not-caught-up What’sOn shows and recorded
  season/episode values. Current live response contains 14 entries.
- Clicking a supported poster opens its service, not a verified show/episode URL.
  Netflix entries remain visible but disabled because Netflix is not configured.
- Server uses GET only, caches in memory for five minutes, and exposes only the
  fields needed by the cards. No tracker updates or API key copying.
- TMDB image host is explicitly allowed for poster loading. Browser verification
  found 13 loaded poster images and all 11 service logos. 19 tests passed.
- BobTV header wordmark enlarged. Full branding/splash/sound direction awaits
  Ken’s choice; no startup sound has been enabled.

## Bob Cinema trial and optional progress

- Continue Watching is now a collapsed, click-to-open panel. No show-list fetch
  occurs at page load; first expansion fetches the existing read-only adapter.
- Ken reports What’sOn progress is stale and plans to refine it separately.
- Bob Cinema option 1 implemented as a replayable on-demand dialog: large white
  and electric-teal wordmark, midnight background, light sweep, original local
  Web Audio chime. No automatic startup sound; this is a trial for Ken to assess.
- Intro auto-closes after 2.8 seconds; Escape/Skip stop sound and return focus.
  Reduced-motion preference disables the reveal/sweep animation.
- Direct Trakt history integration discussed but not configured or authorized
  through OAuth yet; it still depends on history being maintained in Trakt.

## Sidebar layout trial — September 16
- User prefers a workflow with durable project notes and GitHub, similar to their Claude Code setup. GitHub is not connected yet; do not imply it is backed up there.
- User is handling Trakt configuration separately. Continue Watching is now a plain link to https://whatson.kenlill.com/; the landing page no longer requests viewing progress.
- Three-column desktop service grids with left navigation: Home, Continue Watching, United Kingdom, United States. Region menu buttons filter the tiles; launching a service still performs the appropriate connection change. Narrow screens use two columns.
- Renamed the optional Bob Cinema animation/sound trial to Preview intro and moved it to the sidebar. No automatic intro playback.
- Fixed missing Netflix N by resolving SVG class-based colors to explicit fills before bundling.
- Verified the desktop grid has three equal columns with no horizontal overflow, Netflix paths have red fills, the US filter works, and Home restores both regions.
