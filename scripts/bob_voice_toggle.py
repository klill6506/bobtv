"""Start/cancel BobTV voice from a desktop shortcut; authenticated loopback API."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8765'


def toggle(focus=True):
    if focus:
        subprocess.run(['/usr/bin/python3', str(ROOT / 'bobtv.py'), 'home'], check=True, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with urlopen(BASE + '/api/catalog', timeout=3) as response:
        catalog = json.load(response)
    if catalog.get('app') != 'bobtv':
        raise RuntimeError('BobTV is not running on its usual port.')
    with urlopen(BASE + '/api/voice', timeout=3) as response:
        active = json.load(response)['active']
    request = Request(BASE + '/api/voice/' + ('cancel' if active else 'start'), data=b'',
                      headers={'Origin': BASE, 'X-BobTV-Token': catalog['token']})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-focus', action='store_true')
    args = parser.parse_args()
    try:
        toggle(not args.no_focus)
    except Exception as exc:
        subprocess.run(['notify-send', 'BobTV voice', str(exc)], check=False)
        sys.exit(1)
