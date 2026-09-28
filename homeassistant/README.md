# Home Assistant on the BobTV MeLE

Home Assistant Container runs alongside Omarchy and BobTV. The official image
is pinned in `compose.yaml`. Docker starts at boot; the container uses
`restart: unless-stopped`. Container installations do not include Home Assistant
OS's app manager: additional services such as local speech recognition must be
managed separately.

Dashboard: <http://127.0.0.1:8123/>. The owner account is created through the
onboarding screen. Do not put its password or tokens in this repository.

Persistent configuration, accounts, database, and backups are in
`/home/ken/.local/share/homeassistant`, outside Git. The initial configuration
template is copied only once, never over an existing installation.

## Operation

Run from this folder using administrator privileges as required:

```sh
sudo docker compose up -d
sudo docker compose logs --tail=80 homeassistant
sudo docker compose stop
```

`stop` preserves configuration. `up -d` starts the service again.
Before updating the pinned image version, create and download a backup through
Home Assistant's backup interface. After changing the version, run
`sudo docker compose pull` and `sudo docker compose up -d`.

## Setup at work, then at home

The container uses host networking for multicast discovery of local devices.
Host networking does not restrict HTTP access to this computer. Configure and
verify the Home Assistant HTTP listener separately before starting this setup;
`configuration.initial.yaml` does not set a loopback bind address. Hue and both ecobee4
thermostats are configured; ecobee uses local HomeKit Device pairing.

For phone access and discovery at home, review container networking, HTTP
settings in Home Assistant, firewall rules, and NordVPN LAN access. BobTV changes the host VPN when
launching streaming services, so local discovery and device access need testing
with the VPN both on and off. No router port forwarding is needed for local use.

USB/CEC devices and Bluetooth are not passed through yet. Add specific device
access when the corresponding integration is installed.

Official installation instructions:
<https://www.home-assistant.io/installation/linux/#install-home-assistant-container>

## BobTV Smart Home

The BobTV tile and sidebar link open `http://127.0.0.1:8123/bobtv-home/home`.
The native Home Assistant dashboard includes all ten Hue lights and both
thermostats; light icons toggle, brightness sliders dim, and clicking the light
name opens color controls where supported. Thermostat cards adjust setpoints.
Normal Home Assistant login is required in the BobTV Chromium browser profile.

`bobtv-dashboard.yaml` is a source copy; the live YAML dashboard is in the
persistent Home Assistant configuration directory. Its `lovelace.dashboards`
entry registers the `bobtv-home` URL. Listening flashes are configured in
Home Assistant automations.yaml with a private random webhook ID; never copy
the live automation or that ID into Git.

## Doorbell on the TV (September 28)

The Ring integration is set up through Home Assistant's own sign-in page (it
needs the Ring password and a two-factor code, so it is never scripted). It
provides `event.front_door_ding` and `camera.front_door_live_view` for the
Doorbell 3, and a Chime Pro.

On any new ding, the automation `bobtv_doorbell_on_tv` calls
`rest_command.bobtv_doorbell`, which POSTs to BobTV's `/api/doorbell` on
`127.0.0.1:8765` (Home Assistant runs with host networking). The request carries
`X-BobTV-Doorbell`, a random secret kept in two 0600 files outside Git:
`~/.config/bobtv/doorbell.json` for BobTV and `secrets.yaml` here as
`bobtv_doorbell_secret`. The automation triggers on any state change of the
event entity rather than a named event type, so the 2026.4 rename of `ding` to
`ring` does not matter; it ignores changes from `unavailable` so a reconnect is
not a ring.

The live picture is the `doorbell` subview of this dashboard (`/bobtv-home/doorbell`),
a panel with the live camera. The home-screen browser is already signed in to
Home Assistant, so no extra login is needed.

Configuration added to the live files (backups end `.before-doorbell`):

```yaml
# configuration.yaml
rest_command:
  bobtv_doorbell:
    url: http://127.0.0.1:8765/api/doorbell
    method: POST
    headers:
      X-BobTV-Doorbell: !secret bobtv_doorbell_secret
    timeout: 5
```

```yaml
# automations.yaml
- id: bobtv_doorbell_on_tv
  alias: BobTV — doorbell on the TV
  triggers:
  - trigger: state
    entity_id: event.front_door_ding
  conditions:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none
         and trigger.from_state.state != 'unavailable'
         and trigger.to_state.state not in ['unavailable', 'unknown'] }}
  actions:
  - action: rest_command.bobtv_doorbell
  mode: single
  max_exceeded: silent
```

Adding `rest_command` needs a Home Assistant restart; the automation alone
would only need a reload.
