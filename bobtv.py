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


def ensure_region(region):
    if region.get("mode") == "direct":
        if status_fields(vpn("status")).get("status") == "disconnected":
            return
        vpn("disconnect")
        for attempt in range(10):
            if status_fields(vpn("status")).get("status") == "disconnected":
                return
            if attempt < 9:
                time.sleep(1)
        raise ActionError("Could not verify VPN disconnection. Chromium was not opened.")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().with_name("services.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("home", help="Open the full-screen home screen")
    sub.add_parser("serve", help="Run the local home-screen server")
    sub.add_parser("list", help="List stable service IDs and region settings")
    action = sub.add_parser("launch", help="Ensure VPN region, then open the service")
    action.add_argument("service")
    action.add_argument("--check-only", action="store_true", help="Ensure VPN region without opening Chromium")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command in ("home", "serve"):
            import home_server
            return home_server.run(args.command, args.config)
        if args.command == "list":
            for service_id, service in config["services"].items():
                print(f"{service_id}\t{service['name']}\t{service['region']}")
        else:
            state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "bobtv"
            launch(config, args.service, state, args.check_only)
        return 0
    except (ActionError, OSError) as exc:
        print(f"BobTV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
