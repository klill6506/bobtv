#!/usr/bin/env python3
"""Single action entry point for BobTV command, remote, voice and screen clients."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse


class ActionError(Exception):
    pass


def vpn(*args):
    try:
        result = subprocess.run(
            ["nordvpn", *args], capture_output=True, text=True, timeout=90,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        raise ActionError("NordVPN timed out. Chromium was not opened.") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ActionError(f"NordVPN failed: {detail}")
    return result.stdout


def status_fields(output):
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
    fields = dict(
        (key.strip().casefold(), value.strip().casefold())
        for line in output.splitlines() if ":" in line
        for key, value in [line.split(":", 1)]
    )
    return fields


def is_connected(output, country):
    fields = status_fields(output)
    return (fields.get("status") == "connected"
            and fields.get("country") == country.casefold())


def disconnect_vpn():
    if status_fields(vpn("status")).get("status") == "disconnected":
        return
    vpn("disconnect")
    for attempt in range(10):
        if status_fields(vpn("status")).get("status") == "disconnected":
            return
        if attempt < 9:
            time.sleep(1)
    raise ActionError("Could not verify VPN disconnection.")


def ensure_region(region):
    if region.get("mode") == "direct":
        try:
            disconnect_vpn()
        except ActionError as exc:
            raise ActionError(f"{exc} Chromium was not opened.") from exc
        return
    if is_connected(vpn("status"), region["country"]):
        return
    print(f"Connecting NordVPN to {region['country']}…", file=sys.stderr)
    vpn("connect", region["nordvpn_target"])
    for attempt in range(10):
        if is_connected(vpn("status"), region["country"]):
            return
        if attempt < 9:
            time.sleep(1)
    raise ActionError(f"Could not verify a VPN connection to {region['country']}. Chromium was not opened.")


TV_DEFAULTS = {"enabled": False, "address": "0", "hold_seconds": 6, "device": None}


def tv_settings(config):
    return {**TV_DEFAULTS, **config.get("tv", {})}


def cec(settings, commands, hold=None):
    """Send CEC commands through the Pulse-Eight adapter.

    The connection is held open for a moment after the last command because a
    Sony drops an active-source claim made by a client that exits immediately.
    """
    if not shutil.which("cec-client"):
        raise ActionError("cec-client not found; install the libcec package.")
    hold = settings["hold_seconds"] if hold is None else hold
    args = ["cec-client", "-d", "1"]
    if settings["device"]:
        args.append(settings["device"])
    try:
        process = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
    except OSError as exc:
        raise ActionError(f"Could not start cec-client: {exc}") from exc
    try:
        process.stdin.write("".join(f"{command}\n" for command in commands))
        process.stdin.flush()
        time.sleep(hold)
        # cec-client keeps running when its input closes, so ask it to quit.
        process.stdin.write("q\n")
        process.stdin.flush()
        process.stdin.close()
        process.wait(timeout=20)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        process.kill()
        process.wait()
        raise ActionError(f"The CEC adapter did not respond: {exc}") from exc
    if process.returncode:
        detail = (process.stderr.read() or "").strip().splitlines()
        raise ActionError(f"cec-client failed: {detail[-1] if detail else process.returncode}")


def tv_wake(config):
    """Turn the TV on and pull it to BobTV's input."""
    settings = tv_settings(config)
    cec(settings, [f"on {settings['address']}", "as"])


def tv_standby(config):
    settings = tv_settings(config)
    cec(settings, [f"standby {settings['address']}"], hold=2)


def tv_command(config, state):
    settings = tv_settings(config)
    if not settings["enabled"]:
        raise ActionError('TV control is off. Set "enabled": true in the tv section of services.json.')
    if state == "off":
        tv_standby(config)
        print("TV off.")
        return
    if state == "on":
        cec(settings, [f"on {settings['address']}"], hold=2)
        print("TV on.")
        return
    tv_wake(config)
    print("TV on, showing BobTV.")


def load_config(path):
    try:
        config = json.loads(path.read_text())
        browser = config["browser"]
        if not isinstance(browser, list) or not browser or not all(isinstance(x, str) and x for x in browser):
            raise ValueError("browser must be a nonempty argument list")
        for region in config["regions"].values():
            if region.get("mode", "vpn") not in ("vpn", "direct"):
                raise ValueError("invalid region mode")
            if region.get("mode") == "direct":
                continue
            for field in ("country", "nordvpn_target"):
                if not isinstance(region[field], str) or not region[field] or region[field].startswith("-"):
                    raise ValueError(f"invalid region {field}")
        for service_id, service in config["services"].items():
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", service_id):
                raise ValueError("service IDs must use lowercase letters, numbers and hyphens")
            if service["region"] not in config["regions"]:
                raise ValueError(f"unknown region for {service_id}")
            url = urlparse(service["url"])
            if url.scheme != "https" or not url.netloc:
                raise ValueError(f"invalid HTTPS URL for {service_id}")
            if not isinstance(service["name"], str):
                raise ValueError(f"invalid name for {service_id}")
        tv = config.get("tv", {})
        if not isinstance(tv, dict):
            raise ValueError("tv must be an object")
        if set(tv) - set(TV_DEFAULTS):
            raise ValueError(f"unknown tv settings: {sorted(set(tv) - set(TV_DEFAULTS))}")
        if not isinstance(tv.get("enabled", False), bool):
            raise ValueError("tv.enabled must be true or false")
        if not re.fullmatch(r"[0-9a-f]", str(tv.get("address", "0"))):
            raise ValueError("tv.address must be one CEC logical address character")
        hold = tv.get("hold_seconds", TV_DEFAULTS["hold_seconds"])
        if isinstance(hold, bool) or not isinstance(hold, (int, float)) or not 0 <= hold <= 30:
            raise ValueError("tv.hold_seconds must be a number between 0 and 30")
        device = tv.get("device")
        if device is not None and (not isinstance(device, str) or not device.startswith("/dev/")):
            raise ValueError("tv.device must be a path under /dev")
        return config
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ActionError(f"Invalid configuration {path}: {exc}") from exc


def launch(config, service_id, state_dir, check_only=False):
    if service_id not in config["services"]:
        raise ActionError(f"Unknown service '{service_id}'. Run 'bobtv list'.")
    service = config["services"][service_id]
    region = config["regions"][service["region"]]
    for executable in ("nordvpn", config["browser"][0]):
        if not shutil.which(executable):
            raise ActionError(f"Required command not found: {executable}")
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_dir / "action.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ActionError("Another BobTV action is running; try again shortly.") from exc
        ensure_region(region)
        connection = "Home internet (VPN off)" if region.get("mode") == "direct" else region["country"]
        if check_only:
            print(f"Verified: {connection}. Ready to open {service['name']}.")
            return
        if tv_settings(config)["enabled"]:
            # Only after the region is verified: a failed launch must leave the
            # room as it found it. A TV that will not answer must never stop the
            # service from opening.
            try:
                tv_wake(config)
            except (ActionError, OSError) as exc:
                print(f"BobTV: could not control the TV ({exc})", file=sys.stderr)
        with (state_dir / "browser.log").open("ab") as log:
            process = subprocess.Popen(
                [*config["browser"], service["url"]], stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True,
            )
            try:
                code = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                code = None
            if code not in (None, 0):
                raise ActionError(f"Chromium exited with code {code}; see {state_dir / 'browser.log'}")
        print(f"Launched {service['name']} using {connection}.")


def release(state_dir):
    """Turn NordVPN off after a VPN service so Tailscale regains the internet."""
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_dir / "action.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ActionError("Another BobTV action is running; try again shortly.") from exc
        disconnect_vpn()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().with_name("services.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("home", help="Open the full-screen home screen")
    serve = sub.add_parser("serve", help="Run the home-screen server")
    serve.add_argument("--host", default=os.environ.get("BOBTV_HOST", "127.0.0.1"),
                       help="Interface to bind (default 127.0.0.1; use 0.0.0.0 for Tailscale)")
    serve.add_argument("--port", type=int, default=int(os.environ.get("BOBTV_PORT", "8765")))
    sub.add_parser("list", help="List stable service IDs and region settings")
    action = sub.add_parser("launch", help="Ensure VPN region, then open the service")
    action.add_argument("service")
    action.add_argument("--check-only", action="store_true", help="Ensure VPN region without opening Chromium")
    sub.add_parser("release", help="Turn NordVPN off after watching a VPN service")
    tv = sub.add_parser("tv", help="Turn the TV on or off, or pull it to BobTV's input")
    tv.add_argument("state", choices=("on", "off", "here"))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command in ("home", "serve"):
            import home_server
            return home_server.run(args.command, args.config,
                                   host=getattr(args, "host", None), port=getattr(args, "port", None))
        if args.command == "list":
            for service_id, service in config["services"].items():
                print(f"{service_id}\t{service['name']}\t{service['region']}")
        elif args.command == "tv":
            tv_command(config, args.state)
        else:
            state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "bobtv"
            if args.command == "release":
                release(state)
                print("NordVPN is off.")
            else:
                launch(config, args.service, state, args.check_only)
        return 0
    except (ActionError, OSError) as exc:
        print(f"BobTV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
