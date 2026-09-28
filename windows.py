"""Hyprland window handling shared by the doorbell, launching a service and Home.

Every window is addressed by the address Hyprland gave it, never by "the active
window", so closing one thing can never close another. Addresses are validated
before they are spliced into a Hyprland command.
"""
import json
import re
import subprocess
import time

import bobtv

_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


def hyprctl(*args):
    try:
        result = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise bobtv.ActionError(f"hyprctl failed: {exc}") from exc
    if result.returncode:
        raise bobtv.ActionError(f"hyprctl failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def clients():
    try:
        return {c["address"]: c for c in json.loads(hyprctl("-j", "clients") or "[]")}
    except (ValueError, TypeError, KeyError) as exc:
        raise bobtv.ActionError(f"Unreadable window list: {exc}") from exc


def active_window():
    try:
        data = json.loads(hyprctl("-j", "activewindow") or "{}")
    except ValueError as exc:
        raise bobtv.ActionError(f"Unreadable active window: {exc}") from exc
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


def wait_for_new_window(before, timeout=10, sleep=time.sleep):
    """The address of a window that was not in `before`, or None after `timeout` seconds."""
    for _ in range(max(1, int(timeout / 0.25))):
        fresh = sorted(set(clients()) - set(before))
        if fresh:
            return fresh[0]
        sleep(0.25)
    return None


def remember(path, address):
    path.write_text(_address(address))


def forget(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def close_remembered(path):
    """Close the window whose address is stored in `path`, if it is still open.

    Always forgets the address. Returns True only when a window was closed.
    """
    try:
        address = path.read_text().strip()
    except OSError:
        return False
    forget(path)
    try:
        if address in clients():
            close(address)
            return True
    except (bobtv.ActionError, OSError):
        pass
    return False
