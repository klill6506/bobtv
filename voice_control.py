"""Small, local-only voice session supervisor; no speech packages in the web server."""
import json
import os
from pathlib import Path
import signal
import subprocess
import threading

ROOT = Path(__file__).resolve().parent
VOICE_HOME = Path.home() / '.local/share/bobtv/voice'


def resolve_service(text, services):
    """Only complete, unambiguous launch commands may launch a service."""
    import re
    value = re.sub(r'[^a-z0-9 ]', '', text.lower()).strip()
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'^(?:hey )?bob(?: tv)? ', '', value)
    value = re.sub(r'^please ', '', value)
    value = re.sub(r' please$', '', value)
    if value in {'cancel', 'stop', 'never mind', 'nevermind'}:
        return 'cancel'
    value = re.sub(r'^(?:open|launch|start|watch|put on|go to) ', '', value)
    aliases = {
        'bbc': 'bbc-iplayer', 'b b c': 'bbc-iplayer',
        'bbc iplayer': 'bbc-iplayer', 'bbc i player': 'bbc-iplayer',
        'b b c i player': 'bbc-iplayer', 'iplayer': 'bbc-iplayer',
        'prime': 'prime-video', 'prime video': 'prime-video',
        'amazon prime': 'prime-video', 'amazon prime video': 'prime-video',
        'youtube tv': 'youtube-tv', 'you tube tv': 'youtube-tv',
        'you tube': 'youtube', 'youtube': 'youtube',
        'hulu': 'hulu', 'houlou': 'hulu', 'netflix': 'netflix', 'apple tv': 'apple-tv',
        'apple t v': 'apple-tv', 'hbo': 'hbo-max', 'hbo max': 'hbo-max',
        'max': 'hbo-max', 'peacock': 'peacock', 'paramount': 'paramount-plus',
        'paramount plus': 'paramount-plus', 'itv': 'itvx', 'itv x': 'itvx',
        'channel four': 'channel4', 'channel 4': 'channel4',
    }
    result = aliases.get(value)
    return result if result in services else None


class VoiceController:
    def __init__(self, config_path, busy):
        self.config_path = Path(config_path).resolve()
        self.busy = busy
        self.guard = threading.Lock()
        self.process = None
        self.state = {'active': False, 'phase': 'idle', 'message': 'Ready to talk to Bob.', 'heard': ''}

    def status(self):
        with self.guard:
            return dict(self.state)

    def start(self, mode='listen'):
        with self.guard:
            if not self.busy.acquire(blocking=False):
                raise RuntimeError('Bob is already busy. Wait or cancel the voice session.')
            try:
                python = VOICE_HOME / 'venv/bin/python'
                if not python.exists():
                    raise RuntimeError('Bob’s voice is not installed yet.')
                self.process = subprocess.Popen(
                    [str(python), str(ROOT / 'scripts/bob_voice.py'), '--config', str(self.config_path), '--mode', mode],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    start_new_session=True,
                )
                self.state = {'active': True, 'phase': 'starting', 'message': 'Bob is getting ready…', 'heard': ''}
                threading.Thread(target=self._watch, args=(self.process,), daemon=True).start()
            except Exception:
                self.busy.release()
                raise
        return self.status()

    def _watch(self, process):
        timer = threading.Timer(240, lambda: self.cancel(process))
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                try:
                    update = json.loads(line)
                    with self.guard:
                        if self.state['phase'] != 'cancelling':
                            self.state.update({k: str(update[k])[:500] for k in ('phase', 'message', 'heard') if k in update})
                except (ValueError, TypeError):
                    continue
            code = process.wait()
            with self.guard:
                if self.state['phase'] == 'cancelling':
                    self.state.update(phase='idle', message='Cancelled.')
                elif code != 0 and self.state['phase'] != 'error':
                    self.state.update(phase='error', message='Bob’s voice stopped unexpectedly. Try again.')
        finally:
            timer.cancel()
            process.stdout.close()
            with self.guard:
                self.process = None
                self.state['active'] = False
                self.busy.release()

    def cancel(self, expected=None):
        with self.guard:
            if (self.process is not None and self.process.poll() is None
                    and (expected is None or self.process is expected)):
                self.state.update(phase='cancelling', message='Stopping Bob…')
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        return self.status()
