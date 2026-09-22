"""Use BobTV voice on its home screen; otherwise toggle ChatGPT voice."""
import json
import re
import subprocess
import time


def hypr(*args):
    return subprocess.run(['hyprctl', *args], check=True, capture_output=True,
                          text=True, timeout=3).stdout


def main():
    active = json.loads(hypr('-j', 'activewindow'))
    if (active.get('title') in ('BobTV', 'BobTV - Chromium')
            and 'chromium' in active.get('class', '').lower()):
        from bob_voice_toggle import toggle
        toggle(focus=False)
        return
    clients = json.loads(hypr('-j', 'clients'))
    clients = sorted(clients, key=lambda c: c.get('focusHistoryID', 999))
    target = next((c for c in clients if c.get('class') == 'Chatgpt'
                   and c.get('mapped') and not c.get('hidden')), None)
    if target is None:
        subprocess.run(['notify-send', 'BobTV voice', 'Open ChatGPT first, then press Mic.'], check=False)
        return
    address = target['address']
    if not re.fullmatch(r'0x[0-9a-fA-F]+', address):
        raise ValueError('Invalid window address')
    hypr('dispatch', 'hl.dsp.focus({ window = "address:' + address + '" })')
    for _ in range(10):
        if json.loads(hypr('-j', 'activewindow')).get('address') == address:
            break
        time.sleep(.05)
    else:
        raise RuntimeError('ChatGPT could not receive focus')
    try:
        hypr('dispatch', 'hl.dsp.send_key_state({ mods = "CTRL ALT", key = "V", state = "down" })')
        time.sleep(.05)
    finally:
        hypr('dispatch', 'hl.dsp.send_key_state({ mods = "CTRL ALT", key = "V", state = "up" })')


if __name__ == '__main__':
    main()
