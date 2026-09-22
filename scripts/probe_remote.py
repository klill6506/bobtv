"""Capture only MX3 control buttons for 120 seconds, then release the receiver."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import select
import struct
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--one', action='store_true', help='Stop after the first control-button press')
parser.add_argument('--colors', action='store_true', help='Capture red, green, yellow, blue in order, then stop')
parser.add_argument('--edges', action='store_true', help='Show button press/release timing; stop three seconds after release')
parser.add_argument('--mic-test', action='store_true', help='Wait for Home, then observe the mic button for 20 seconds')
args = parser.parse_args()

names = {}
for line in Path('/usr/include/linux/input-event-codes.h').read_text().splitlines():
    match = re.match(r'#define\s+((?:KEY|BTN)_\w+)\s+(0x[0-9a-fA-F]+|[0-9]+)\b', line)
    if match:
        names[int(match[2], 0)] = match[1]
# Never report letters, numbers, or typed text.
allowed = {1, 28, 96, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
           113, 114, 115, 116, 119, 127, 128, 139, 158, 159, 164, 166, 172,
           173, 174, 207, 217, 226, 272, 273, 582}
allowed.update(range(59, 69))  # F1–F10
allowed.update({87, 88, *range(183, 195), *range(398, 402)})
event = struct.Struct('llHHi')
opened = []
try:
    for node in sorted(Path('/sys/class/input').glob('event*')):
        device = node / 'device'
        if ((device / 'id/vendor').read_text().strip() != '1915'
                or (device / 'id/product').read_text().strip() != '1025'):
            continue
        fd = os.open('/dev/input/' + node.name, os.O_RDONLY | os.O_NONBLOCK)
        opened.append(fd)
        fcntl.ioctl(fd, 0x40044590, 1)  # EVIOCGRAB; released on close
    if not opened:
        raise RuntimeError('MX3 receiver not found')
    colors = iter(['RED', 'GREEN', 'YELLOW', 'BLUE'])
    captured = 0
    print('READY: press HOME once, then hold MIC for three seconds and release.' if args.mic_test else 'READY: hold the MIC button for three seconds, then release.' if args.edges else 'READY: press RED, GREEN, YELLOW, BLUE once each, in order.' if args.colors else 'READY: press the requested control button.' if args.one else 'READY: press Home, Back, Up, Down, Left, Right, OK, Volume Up, Volume Down, Play/Pause in order.', flush=True)
    started = time.monotonic()
    deadline = time.monotonic() + (300 if args.mic_test else 120)
    while time.monotonic() < deadline:
        ready, _, _ = select.select(opened, [], [], min(1, deadline-time.monotonic()))
        for fd in ready:
            data = os.read(fd, event.size * 64)
            for offset in range(0, len(data), event.size):
                _, _, kind, code, value = event.unpack_from(data, offset)
                if (args.edges or args.mic_test) and kind == 1 and code in allowed:
                    # Report only control buttons, including KEY_VOICECOMMAND.
                    label = names.get(code, str(code))
                    print(f'{time.monotonic()-started:.2f}s {label} value={value}', flush=True)
                    if args.mic_test and code == 172 and value == 1:
                        deadline = min(deadline, time.monotonic() + 20)
                        print('HOME received; now hold MIC for three seconds and release.', flush=True)
                    elif args.edges and value == 0:
                        deadline = min(deadline, time.monotonic() + 3)
                    continue
                if kind == 1 and value == 1 and code in allowed:
                    label = next(colors) + ': ' if args.colors else ''
                    print(label + names.get(code, str(code)), flush=True)
                    captured += 1
                    if args.one or (args.colors and captured == 4):
                        raise SystemExit(0)
finally:
    for fd in opened:
        os.close(fd)
    print('FINISHED: remote released.', flush=True)
