# iPhone button remote

The installed `bobtv-remote.service` runs at graphical login and binds to the LAN address in `~/.config/bobtv/remote.env`. The original home server stays on loopback port 8765.

Connect the iPhone to the same home Wi-Fi. Print its private pairing link:

```sh
python3 remote_server.py --host 192.168.86.226 --url
```

Open that full link in Safari, or encode it locally with `qrencode` and scan it. Use Safari's Share → Add to Home Screen to save the remote. Keep the fragment in the saved link; it carries pairing into an iOS standalone shortcut. The pairing link grants button control, so keep it private. No app or Bluetooth pairing is needed.

Buttons launch the configured services on the TV, return Home, toggle playback, adjust volume, and mute. Playback uses Omarchy's active media player; sites must expose media controls for it to work. Launching a service still performs BobTV's existing VPN region change and can affect other streams. No pointer, keyboard, title search, or sign-in control is provided.

The LAN server only serves its three static assets plus authenticated catalog and button endpoints. Requests require a persistent random pairing token; actions also require the exact local Origin and Host. It is HTTP for a trusted home network only; do not forward port 8766 to the internet. NordVPN LAN Discovery is already enabled on this computer.

To check or stop it:

```sh
systemctl --user status bobtv-remote.service
systemctl --user disable --now bobtv-remote.service
```

If the TV's DHCP address changes, update `BOBTV_REMOTE_HOST` in `~/.config/bobtv/remote.env`, restart the service, and print a new link using that address. A DHCP reservation in the router avoids this. To revoke pairing, stop the service, remove `~/.local/state/bobtv/remote-token`, and start it again; old links will no longer authenticate.

Validation: full suite passed (42 tests), remote tests re-passed after LAN startup fixes, and the live browser paired, loaded channels, and sent mute/unmute commands. Actual iPhone/Safari pairing remains a user-side check.
