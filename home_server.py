"""Loopback-only BobTV home screen. Actions use the shared command layer."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
import bobtv
import whatson

ROOT = Path(__file__).resolve().parent
PORT = 8765
BASE = f'http://127.0.0.1:{PORT}'


def make_server(config_path, port=PORT):
    token = secrets.token_urlsafe(32)
    busy = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, data, kind='application/json'):
            body = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' https://image.tmdb.org; media-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.reply(403, {'error': 'Invalid host'})
                return False
            return True

        def do_GET(self):
            if not self.valid_host(): return
            try:
                if self.path == '/api/catalog':
                    config = bobtv.load_config(config_path)
                    self.reply(200, {'app': 'bobtv', 'token': token, 'services': config['services']})
                elif self.path == '/api/continue':
                    self.reply(200, whatson.shows())
                elif self.path == '/api/status':
                    fields = bobtv.status_fields(bobtv.vpn('status'))
                    if fields.get('status') == 'connected':
                        label = 'VPN · ' + fields.get('country', 'Unknown country').title()
                    elif fields.get('status') == 'disconnected':
                        label = 'Home internet · VPN off'
                    else:
                        raise bobtv.ActionError('VPN status unavailable')
                    self.reply(200, {'label': label})
                else:
                    files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
                    branding = {
                        '/branding/background.png': ('artwork/bobtv-background-dark-4k.png', 'image/png'),
                        '/branding/logo.png': ('artwork/bobtv-logo.png', 'image/png'),
                        '/branding/icon.png': ('artwork/bobtv-icon.png', 'image/png'),
                        '/branding/splash.png': ('artwork/bobtv-splash.png', 'image/png'),
                        '/branding/startup.wav': ('sound/bobtv-startup-sunrise-v1.wav', 'audio/wav'),
                    }
                    if self.path in branding:
                        name, kind = branding[self.path]
                        self.reply(200, (ROOT / 'assets' / 'branding' / name).read_bytes(), kind)
                        return
                    if self.path not in files:
                        self.reply(404, {'error': 'Not found'}); return
                    name, kind = files[self.path]
                    self.reply(200, (ROOT / 'web' / name).read_bytes(), kind)
            except (bobtv.ActionError, OSError, ValueError) as exc:
                self.reply(503, {'error': str(exc)})

        def do_POST(self):
            if not self.valid_host(): return
            if (self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}'
                    or not secrets.compare_digest(self.headers.get('X-BobTV-Token', ''), token)):
                self.reply(403, {'error': 'Untrusted request'}); return
            if self.path != '/api/launch':
                self.reply(404, {'error': 'Not found'}); return
            if not busy.acquire(blocking=False):
                self.reply(409, {'error': 'A service is already opening. Please wait.'}); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024: raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                service = data.get('service')
                config = bobtv.load_config(config_path)
                if not isinstance(service, str) or service not in config['services']:
                    raise ValueError('Unknown service')
                state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'bobtv'
                bobtv.launch(config, service, state)
                self.reply(200, {'message': 'Opened ' + config['services'][service]['name'] + '. Close its window to return home.'})
            except (ValueError, AttributeError, bobtv.ActionError, OSError) as exc:
                self.reply(400, {'error': str(exc)})
            finally:
                busy.release()

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def run(command, config_path):
    if command == 'serve':
        make_server(config_path).serve_forever()
        return 0
    try:
        with urlopen(BASE + '/api/catalog', timeout=2) as response:
            if json.load(response).get('app') != 'bobtv':
                raise bobtv.ActionError('Port 8765 is occupied by another application.')
    except OSError:
        state = Path.home() / '.local/state/bobtv'
        state.mkdir(parents=True, exist_ok=True)
        managed = (Path.home() / '.config/systemd/user/bobtv-home.service').exists()
        process = None
        if managed:
            result = subprocess.run(['systemctl', '--user', 'start', 'bobtv-home.service'], capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise bobtv.ActionError('Could not start the BobTV service: ' + result.stderr.strip())
        else:
            with (state / 'home.log').open('ab') as log:
                process = subprocess.Popen([sys.executable, str(ROOT / 'bobtv.py'), '--config', str(config_path.resolve()), 'serve'], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(40):
            if process is not None and process.poll() is not None:
                raise bobtv.ActionError('Home server could not start; see ~/.local/state/bobtv/home.log')
            try:
                with urlopen(BASE + '/api/catalog', timeout=1) as response:
                    if json.load(response).get('app') == 'bobtv': break
            except OSError:
                time.sleep(.1)
        else: raise bobtv.ActionError('Home server did not become ready.')
    subprocess.Popen(['chromium', '--user-data-dir=' + str(Path.home() / '.local/share/bobtv/home-browser'), '--no-first-run', '--kiosk', BASE], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print('Opened BobTV home. Alt+F4 closes the home window.')
    return 0
