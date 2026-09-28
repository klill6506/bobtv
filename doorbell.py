"""Show the front-door camera on the TV when the doorbell rings.

Home Assistant calls POST /api/doorbell on the home server (loopback only, with a
shared secret). This module puts the live camera in front of whatever is on
screen, wakes the TV and takes its input, then after a while takes the camera
away and puts things back as they were. A TV that was off goes back to standby,
so a late-night ring does not leave it on all night.

The camera is a Home Assistant dashboard view opened in the home-screen browser,
which is already signed in to Home Assistant. Windows are handled through
Hyprland, and every window is addressed by the address Hyprland gave it, never
"the active window", so the camera can never close the show underneath.
"""
import fcntl
import json
import logging
from pathlib import Path
import re
import subprocess
import time

import bobtv

SECRET_FILE = Path.home() / ".config/bobtv/doorbell.json"
HOME_PROFILE = Path.home() / ".local/share/bobtv/home-browser"
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
_log = logging.getLogger(__name__)


def load_secret(path=SECRET_FILE):
    """The secret Home Assistant sends. None when missing, unreadable or too short."""
    try:
        value = json.loads(Path(path).read_text()).get("secret")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and len(value) >= 32 else None


def hyprctl(*args):
    try:
        result = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise bobtv.ActionError(f"hyprctl failed: {exc}") from exc
    if result.returncode:
        raise bobtv.ActionError(f"hyprctl failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def clients():
    return {c["address"]: c for c in json.loads(hyprctl("-j", "clients") or "[]")}


def active_window():
    data = json.loads(hyprctl("-j", "activewindow") or "{}")
    return data if isinstance(data, dict) and data.get("address") else None


def _address(value):
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise bobtv.ActionError(f"Refusing an unexpected window address: {value!r}")
    return value


def focus(address):
    hyprctl("dispatch", 'hl.dsp.focus({ window = "address:' + _address(address) + '" })')


def make_fullscreen():
    """Fullscreen the active window. Call only straight after focus()."""
    hyprctl("dispatch", 'hl.dsp.window.fullscreen({ mode = "fullscreen" })')


def close(address):
    hyprctl("dispatch", 'hl.dsp.window.close({ window = "address:' + _address(address) + '" })')


def open_camera(url):
    subprocess.Popen(
        ["chromium", "--user-data-dir=" + str(HOME_PROFILE), "--new-window", url],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_new_window(before, timeout=10, sleep=time.sleep):
    for _ in range(int(timeout / 0.25)):
        fresh = sorted(set(clients()) - set(before))
        if fresh:
            return fresh[0]
        sleep(0.25)
    return None


def show(config, state_dir, sleep=time.sleep, clock=time.monotonic):
    """Put the front door on the TV for a while, then put everything back.

    Returns a short description of what happened. A second ring while the camera
    is already up does nothing, so repeated presses never stack windows.
    """
    settings = bobtv.doorbell_settings(config)
    if not settings["enabled"]:
        raise bobtv.ActionError('Doorbell display is off. Set "enabled": true in the doorbell section of services.json.')
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_dir / "doorbell.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "The front door is already on screen."
        before = clients()
        previous = active_window()
        open_camera(settings["url"])
        window = wait_for_new_window(before, sleep=sleep)
        if window is None:
            raise bobtv.ActionError("The camera window never appeared.")
        # The camera goes in front first; the TV steps take several seconds.
        focus(window)
        if not clients().get(window, {}).get("fullscreen"):
            make_fullscreen()
        deadline = clock() + settings["seconds"]

        was_off = False
        if bobtv.tv_settings(config)["enabled"]:
            try:
                # Only a definite "standby" counts as off. When the TV will not say,
                # never turn it off afterwards: someone may be watching.
                was_off = bobtv.tv_power(config) == "standby"
            except (bobtv.ActionError, OSError) as exc:
                _log.warning("Doorbell: could not read TV power (%s)", exc)
            try:
                bobtv.tv_wake(config)
            except (bobtv.ActionError, OSError) as exc:
                _log.warning("Doorbell: could not wake the TV (%s)", exc)

        sleep(max(0, deadline - clock()))

        # If someone closed the camera themselves they are using the TV, so leave
        # the room exactly as they left it.
        still_open = window in clients()
        if not still_open:
            return "The camera was closed by hand; nothing else changed."
        close(window)
        if previous and previous["address"] in clients():
            focus(previous["address"])
            if previous.get("fullscreen"):
                make_fullscreen()
        if was_off:
            try:
                bobtv.tv_standby(config)
            except (bobtv.ActionError, OSError) as exc:
                _log.warning("Doorbell: could not put the TV back to standby (%s)", exc)
            return "Showed the front door, then put the TV back to standby."
        return "Showed the front door."


def run_quietly(config, state_dir):
    """For the home server's background thread: never raise, always log."""
    try:
        message = show(config, state_dir)
        _log.info("Doorbell: %s", message)
    except (bobtv.ActionError, OSError, ValueError) as exc:
        _log.warning("Doorbell: %s", exc)
