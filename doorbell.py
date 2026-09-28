"""Show the front-door camera on the TV when the doorbell rings.

Home Assistant calls POST /api/doorbell on the home server (loopback only, with a
shared secret). This module pauses whatever is playing on BobTV, puts the live
camera in front, wakes the TV and takes its input, then after a while takes the
camera away and puts things back as they were: the window in front, its
fullscreen, and playback. A TV that was off goes back to standby, so a
late-night ring does not leave it on all night.

The camera is a Home Assistant dashboard view opened in the home-screen browser,
which is already signed in to Home Assistant. Window handling is in windows.py.
"""
import fcntl
import json
import logging
from pathlib import Path
import subprocess
import time

import bobtv
import windows

SECRET_FILE = Path.home() / ".config/bobtv/doorbell.json"
HOME_PROFILE = Path.home() / ".local/share/bobtv/home-browser"
CAMERA_FILE = "doorbell-window"  # in the state dir, so Home can dismiss the camera
_log = logging.getLogger(__name__)


def load_secret(path=SECRET_FILE):
    """The secret Home Assistant sends. None when missing, unreadable or too short."""
    try:
        value = json.loads(Path(path).read_text()).get("secret")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and len(value) >= 32 else None


def open_camera(url):
    subprocess.Popen(
        ["chromium", "--user-data-dir=" + str(HOME_PROFILE), "--new-window", url],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def media(action):
    """Omarchy's own media control: status, pause or play. Returns its output, or None."""
    try:
        result = subprocess.run(["omarchy-shell", "media", action], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def media_playing():
    """True only when Omarchy reports something actually playing."""
    try:
        return json.loads(media("status") or "{}").get("playing") is True
    except ValueError:
        return False


def pause_playback():
    """Pause whatever is playing on BobTV. True if something was paused."""
    if media_playing() and media("pause") == "ok":
        return True
    return False


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
        before = windows.clients()
        previous = windows.active_window()
        paused = pause_playback()
        open_camera(settings["url"])
        window = windows.wait_for_new_window(before, sleep=sleep)
        if window is None:
            if paused:
                media("play")
            raise bobtv.ActionError("The camera window never appeared.")
        windows.remember(state_dir / CAMERA_FILE, window)
        try:
            # The camera goes in front first; the TV steps take several seconds.
            windows.focus(window)
            if not windows.clients().get(window, {}).get("fullscreen"):
                windows.make_fullscreen()
            deadline = clock() + settings["seconds"]

            was_off = False
            if bobtv.tv_settings(config)["enabled"]:
                try:
                    # Only a definite "standby" counts as off. When the TV will not
                    # say, never turn it off afterwards: someone may be watching.
                    was_off = bobtv.tv_power(config) == "standby"
                except (bobtv.ActionError, OSError) as exc:
                    _log.warning("Doorbell: could not read TV power (%s)", exc)
                try:
                    bobtv.tv_wake(config)
                except (bobtv.ActionError, OSError) as exc:
                    _log.warning("Doorbell: could not wake the TV (%s)", exc)

            sleep(max(0, deadline - clock()))

            # If someone closed the camera themselves (or pressed Home) they are
            # using the TV, so leave the room exactly as they left it.
            if window not in windows.clients():
                return "The camera was closed by hand; nothing else changed."
            windows.close(window)
            if previous and previous["address"] in windows.clients():
                windows.focus(previous["address"])
                if previous.get("fullscreen"):
                    windows.make_fullscreen()
            if paused:
                media("play")
            if was_off:
                try:
                    bobtv.tv_standby(config)
                except (bobtv.ActionError, OSError) as exc:
                    _log.warning("Doorbell: could not put the TV back to standby (%s)", exc)
                return "Showed the front door, then put the TV back to standby."
            return "Showed the front door, then resumed playback." if paused else "Showed the front door."
        finally:
            windows.forget(state_dir / CAMERA_FILE)


def run_quietly(config, state_dir):
    """For the home server's background thread: never raise, always log."""
    try:
        message = show(config, state_dir)
        _log.info("Doorbell: %s", message)
    except (bobtv.ActionError, OSError, ValueError) as exc:
        _log.warning("Doorbell: %s", exc)
