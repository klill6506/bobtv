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

## GitHub and branding handoff — September 16
- GitHub CLI authenticated as klill6506 using the OS keyring.
- Private repository created: https://github.com/klill6506/bobtv ; origin tracks master. First project checkpoint pushed. This supersedes the earlier note that GitHub was not connected.
- Shared branding folders: assets/branding/artwork, assets/branding/sound, assets/branding/concepts. Each is visible on GitHub with a README; the parent README documents naming and handoff.
- Assets uploaded from other devices are not automatically deployed. Review Ken’s choice before wiring artwork/audio into the live interface.

## Sunrise branding integrated — September 16
- Pulled the supplied dark 4K background and integrated it with the transparent logo, blue selection colors and warm gold focus rings. Retained sidebar, three-column desktop grids and What’sOn link.
- Approved splash image and WAV master replace the synthesized Bob Cinema trial. Fade intro lasts 4.1 seconds, once per tab session with manual Preview intro. Browser-blocked autoplay falls back to a silent intro with explanation. No global browser autoplay policy changed.
- Exact branding route allowlist serves only the five needed assets; uploaded scripts and arbitrary paths remain inaccessible.
- Validation: 20 Python tests passed, JS syntax passed; browser confirmed logo/background loading, three columns, recorded audio playing, automatic close, skip stopping audio/restoring focus, and no repeat on refresh. Physical TV audio still needs the at-home test.

## Audio and navigation fixes — September 16
- HDMI output to SONY TV was at 40%; raised to 80%. Intro HTML audio was at 50%; now 100%. Physical listening confirmation remains with Ken.
- Prime tile now targets https://www.primevideo.com/ instead of Amazon's video storefront. Account playback has not been retested.
- Installed Ctrl+Alt+H for bobtv home in user bindings.lua; backup is bindings.lua.before-bobtv. Hyprland reload succeeded without config errors.
- Home action focuses an existing Chromium BobTV window. Verified a second invocation returned to the existing window. Alt+Tab remains the existing app switcher.
- Home footer displays controls; directional keys no longer scroll the page when focus hits an edge. Streaming sites retain their own controls. Remote button mapping awaits input-device details.
- Validation: 22 Python tests passed and JavaScript syntax passed.

## Longer sunrise sound — September 17
- Ken requested a longer splash sound. Created a six-second v2 WAV from v1 using pitch-preserving Rubber Band stretching; retained the motif and original file. Reproduction script is in sound/source/extend_take.py.
- Active audio route now serves v2; splash animation and close timer both last 6.3 seconds. Skip/Escape and once-per-session behavior remain.
- Verified generated duration and JavaScript syntax. Physical listening feedback is pending.

## MX3 remote setup — September 17
- Ken plugged in the MX3 Air Fly Mouse and confirmed pointer movement. Linux identifies its receiver as XING WEI 2.4G USB, USB 1915:1025.
- Keyboard, mouse, consumer-control and system-control interfaces are present. Existing Omarchy bindings handle standard volume and media key symbols; the remote's actual button codes still need measurement.
- Added scripts/probe_remote.py for a bounded 60-second exclusive test of this receiver only. Reports allowlisted control buttons, not typed text; all grabs release on exit. Device access requires administrator authentication.
- No remote-specific bindings have been installed yet. Ctrl+Alt+H remains available for BobTV Home.

### MX3 Home button identified and configured
- Live button test received KEY_HOMEPAGE (172). Installed XF86HomePage → /home/ken/.local/bin/bobtv home in user bindings.lua; no previous mapping existed. Backup: bindings.lua.before-mx3.
- Hyprland reload and shortcut validation completed. Physical return-to-home check is pending. Back and other remote buttons have not yet been measured.
- Probe duration is now 120 seconds. Its output can be saved to /tmp/bobtv-mx3-test.log so an interrupted conversation does not lose control-button results.

### MX3 Home confirmed; audio diagnosis
- Ken confirmed the remote Home button returns to BobTV.
- Reported missing sound. Live inspection found analog stereo at 40%, unmuted, instead of the previously used SONY HDMI output. All HDMI audio ports report unavailable and ALSA ELD reports no monitor. Saved default still names HDMI. No audio routing changes made pending confirmation of current display/speaker connection.
- MX3 USB audio interface is microphone-input-only, not a playback sink.

### MX3 color-button request — not installed
- Desired mapping: red BBC iPlayer, green Prime Video, yellow YouTube TV, blue Hulu. Ken completed the color-button test; no allowlisted control-key events were captured.
- Aerb MX3 manual identifies the four colors as IR-learning buttons: https://upload.sunsky-online.com/res/drivers/S-KB-0069_MX3_User_Manual.pdf . This likely explains the lack of USB events; exact MX3 variant is not independently confirmed.
- Color shortcuts were not installed. Alternatives are other USB-reporting buttons or an added IR receiver; await Ken's preference. Home remains configured and user-confirmed.

### MX3 microphone capture test
- Ken plans to leave the MeLE at home once setup is complete.
- Captured 30 seconds locally from the explicit XING WEI USB mono microphone, 8 kHz/16-bit, to /tmp/bobtv-mx3-mic-test.wav. Recording has ended.
- WAV duration and decoding verified; non-silent signal with varying levels was recorded. Brief peaks reached full scale. Speech intelligibility and mic-button hold/toggle behavior still need listening confirmation; no speech recognition or voice actions configured.

### MX3 Mic button configured — app restart and live test pending
- Comparison capture confirmed Home down/up, followed by KEY_VOICECOMMAND (582) down/up only 0.12 seconds apart during a requested three-second hold. Use a voice toggle, not hold-to-talk.
- Installed XF86VoiceCommand → scripts/remote_voice.py. Script focuses the existing Chatgpt window, verifies focus, and sends Ctrl+Alt+V with paired down/up events. If ChatGPT is not open, it shows a notification.
- Configured realtimeVoice=Ctrl+Alt+V in ~/.codex/keybindings.json, using the schema confirmed in installed app code. The controller toggles voice sessions; reads the binding on app startup. ChatGPT must be fully quit and reopened before physical verification.
- Hyprland reload/configerrors clean; Home/Mic entries present. Mock checks passed for focus-before-send, paired key events, and refusal to send to unrelated windows.
- This controls ChatGPT voice; BobTV/Home Assistant command recognition is not yet configured.

## Home Assistant installation started — September 17
- Ken confirmed MX3 mic-to-ChatGPT voice works after restart.
- Ken authorized installing Home Assistant; MeLE will stay home after setup. Docker Engine 29.7.2 and Compose 5.5.1 are installed. Enabled docker.service at boot and started it.
- Prepared homeassistant/compose.yaml using official image 2026.9.2, host networking, restart unless-stopped, 60s shutdown grace period, capped logs. No privileged/device/DBus passthrough yet.
- Created initial persistent config at ~/.local/share/homeassistant outside Git; HTTP binds 127.0.0.1:8123 during work setup. No owner account created.
- Added Home Assistant sidebar link. Compose schema and git diff checks passed.
- Pending: pkexec docker compose up -d is awaiting Linux authentication (exec session 41468). Do not claim installation complete until container and HTTP checks pass. Then open local onboarding for Ken to create the owner account.

## Desktop startup and Home Assistant follow-up — September 17
- Added o.launch_on_start("chatgpt") to ~/.config/hypr/autostart.lua for ChatGPT/Codex at desktop login. Added explicit input.numlock_by_default=true to user input.lua (the Omarchy default already enabled it). Timestamped backups made; reload succeeded and configerrors was empty. Next-login launch has not yet been tested.
- Home Assistant installation completed; onboarding API responds and Docker service is enabled/active. Owner account remains uncreated.
- Observed HTTP listening on all interfaces despite initial YAML server_host setting. Current HA has migrated HTTP settings to UI storage. Compose now publishes only 127.0.0.1:8123 using bridge networking; this limits discovery until home network setup. Initial template no longer includes deprecated HTTP YAML.
- Applying updated compose awaits Linux authentication in exec session 26978; inspect session 69086 also pending. Verify loopback listener and onboarding after completion. Do not describe local-only networking as applied until verified.

### Home Assistant setup connection verified
- Ken completed authentication; compose session 26978 exited successfully and recreated/started homeassistant with bridge networking.
- Verified HTTP listens only on 127.0.0.1:8123 and /api/onboarding responds with owner setup incomplete. Ready for Ken to create the account.
- Saved Wi-Fi profiles Downstairs 2.0 and Occam's Router both have autoconnect enabled. No Wi-Fi settings changed.

## BobTV speaking milestone — September 17
- Added local push-to-talk worker, service-name parsing, spoken replies, ten-second capture limit, cancellation and four-minute watchdog. Explicit MX3 microphone; no microphone recordings saved/uploaded.
- Home now has Talk to Bob, Hear Bob, Cancel, and live status/transcript. Voice POSTs retain origin/token/host checks and share the menu busy lock.
- MX3 Mic routes to BobTV only on its Chromium home screen; elsewhere keeps ChatGPT behavior. Added Ctrl+Alt+B, backed up bindings.lua, reloaded/validated Hyprland.
- Isolated packages/models installed under ~/.local/share/bobtv/voice. Vosk handles confident service commands; local Whisper base.en supplies fallback; uncertain matched services require spoken yes. Piper Alan is currently active.
- 36 automated tests passed. Synthetic speech at 8kHz bandwidth passed BBC, Prime, Hulu (confirmation required), YouTube TV, negated BBC, unsupported Grantchester, and silence. Physical command recognition still needs Ken's test.
- Browser Hear Bob test completed; Ken confirmed hearing the greeting. Menu service restarted with final changes. Hue effects and title/episode search remain future work.
- Ken requested Marin. Official OpenAI docs confirm gpt-4o-mini-tts supports Marin. No API key was present in this process or project .env. No paid API requests made.
- Prepared scripts/setup_marin.py: terminal hidden key input, one-time fixed-reply generation, local WAV reuse, activation after every phrase succeeds. Key not stored. Current voice stays active pending API setup; asked Ken whether he already has a key. Marin is prepared but NOT yet activated.

## Marin activated — September 17
- Ken supplied `~/.config/bobtv/bob.env` by USB and authorized completing setup. Restricted the file to 0600; no credentials copied into the repository or logs.
- Generated all 40 fixed replies using OpenAI gpt-4o-mini-tts with Marin, checked each WAV, and activated the local cache. Existing speech delivery instructions retained; imported realtime assistant instructions are not needed for these fixed replies.
- Played the greeting successfully through the actual BobTV voice worker and PipeWire. Ken's listening confirmation is pending. Cached playback needs no API calls; uncached future replies still fall back to Piper.
- MeLE identified as Quieter 4C. CPU measured 77°C against a reported 105°C limit during the heat check; this is not a case-surface measurement. Ken clarified the case was less hot than first described and requested finishing before shutdown.


## Repository review — September 21
- Restored voice API integration, home-window reuse, and the six-second audio route that were missing from the changed home server.
- Forwarded serve host/port CLI options; required a password for non-loopback listeners, enforced exact request origins, and kept voice controls local-only. Unicode passwords are supported.
- Restricted all remote probe modes to control-button events; ordinary typing is excluded.
- Validation: 57 Python tests passed, including remote authentication and integration regressions; both JavaScript files passed syntax checks. Hardware playback, microphone recognition, and iPhone operation were not exercised during this review.
