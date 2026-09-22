"""BobTV home screen. Actions use the shared command layer.

Local mode (default): listens on 127.0.0.1 only, no password needed.

Remote mode (e.g. over Tailscale): set BOBTV_HOST=0.0.0.0,
BOBTV_ALLOWED_HOSTS to the Tailscale IP and/or MagicDNS name
(comma-separated), and BOBTV_PASSWORD to require a password from any
client that is not on the MeLE itself. The browser will prompt for the
password once; the kiosk Chromium on the MeLE is unaffected.
"""
import base64
import binascii
import ipaddress
import json
import os
import re
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
from voice_control import VoiceController

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get('BOBTV_HOST', '127.0.0.1')
PORT = int(os.environ.get('BOBTV_PORT', '8765'))
BASE = f'http://127.0.0.1:{PORT}'
PASSWORD = os.environ.get('BOBTV_PASSWORD', '')
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}


def _tailscale_ips():
    """Tailscale IPs, auto-allowed as Host values when the CLI is present."""
    try:
        out = subprocess.run(['tailscale', 'ip'], capture_output=True,
                             text=True, timeout=5).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def allowed_names(port):
    names = set(LOOPBACK)
    extra = os.environ.get('BOBTV_ALLOWED_HOSTS', '')
    names.update(h.strip().lower() for h in extra.split(',') if h.strip())
    names.update(ip.lower() for ip in _tailscale_ips())
    with_port = {f'{n}:{port}' for n in names}
    return names | with_port


def make_server(config_path, port=PORT, host=HOST):
    token = secrets.token_urlsafe(32)
    busy = threading.Lock()
    voice = VoiceController(config_path, busy)
    allowed = allowed_names(port)
    remote = host not in ('127.0.0.1', 'localhost', '::1')

    if remote and not PASSWORD:
        raise bobtv.ActionError('Set BOBTV_PASSWORD before listening on a non-loopback address.')

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

        def client_is_local(self):
            try:
                return ipaddress.ip_address(self.client_address[0]).is_loopback
            except ValueError:
                return False

        @staticmethod
        def _bare(host_header):
            return host_header.rsplit(':', 1)[0].strip('[]').lower()

        def valid_host(self):
            host = self.headers.get('Host', '')
            if host not in allowed and self._bare(host) not in allowed:
                self.reply(403, {'error': 'Invalid host'})
                return False
            return True

        def authorized(self):
            if self.client_is_local() or not PASSWORD:
                return True
            auth = self.headers.get('Authorization', '')
            ok = False
            if auth.startswith('Basic '):
                try:
                    decoded = base64.b64decode(auth[6:]).decode('utf-8', 'ignore')
                except (ValueError, binascii.Error, UnicodeError):
                    decoded = ''
                _, _, pw = decoded.partition(':')
                ok = secrets.compare_digest(pw.encode('utf-8'), PASSWORD.encode('utf-8'))
            if not ok:
                body = json.dumps({'error': 'Authentication required'}).encode()
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="BobTV"')
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return False
            return True

        def do_GET(self):
            if not self.valid_host(): return
            if not self.authorized(): return
            try:
                if self.path == '/api/catalog':
                    config = bobtv.load_config(config_path)
                    self.reply(200, {'app': 'bobtv', 'token': token, 'services': config['services']})
                elif self.path == '/api/voice':
                    if not self.client_is_local():
                        self.reply(403, {'error': 'Local only'}); return
                    self.reply(200, voice.status())
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
                        '/branding/startup.wav': ('sound/bobtv-startup-sunrise-v2-long.wav', 'audio/wav'),
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
            if not self.authorized(): return
            origin = self.headers.get('Origin', '')
            if (origin != 'http://' + self.headers.get('Host', '')
                    or not secrets.compare_digest(self.headers.get('X-BobTV-Token', ''), token)):
                self.reply(403, {'error': 'Untrusted request'}); return
            if self.path in ('/api/voice/start', '/api/voice/test', '/api/voice/cancel'):
                if not self.client_is_local():
                    self.reply(403, {'error': 'Local only'}); return
                try:
                    if self.path.endswith('/cancel'):
                        result = voice.cancel()
                    else:
                        result = voice.start('test' if self.path.endswith('/test') else 'listen')
                    self.reply(200, result)
                except (RuntimeError, OSError) as exc:
                    self.reply(409, {'error': str(exc)})
                return
            if self.path == '/api/release':
                # Only the TV's own home window, never a remote client mid-show.
                if not self.client_is_local():
                    self.reply(403, {'error': 'Local only'}); return
                if not busy.acquire(blocking=False):
                    self.reply(409, {'error': 'A service is already opening. Please wait.'}); return
                try:
                    bobtv.release(Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'bobtv')
                    self.reply(200, {'message': 'Welcome back. VPN is off.'})
                except (bobtv.ActionError, OSError) as exc:
                    self.reply(400, {'error': str(exc)})
                finally:
                    busy.release()
                return
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

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.voice = voice
    return server


def focus_home():
    """Reuse the home window, including when a streaming window covers it."""
    try:
        result = subprocess.run(['hyprctl', '-j', 'clients'], capture_output=True, text=True, timeout=3, check=True)
        for client in json.loads(result.stdout):
            if client.get('title') not in ('BobTV', 'BobTV - Chromium'):
                continue
            if 'chromium' not in client.get('class', '').lower():
                continue
            address = client.get('address', '')
            if not re.fullmatch(r'0x[0-9a-fA-F]+', address):
                continue
            result = subprocess.run(['hyprctl', 'dispatch', 'hl.dsp.focus({ window = "address:' + address + '" })'], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return True
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return False


def run(command, config_path, host=None, port=None):
    host = host or HOST
    port = port or PORT
    probe_host = '127.0.0.1' if host in ('0.0.0.0', '::') else host
    probe = f'http://{probe_host}:{port}'
    if command == 'serve':
        make_server(config_path, port=port, host=host).serve_forever()
        return 0
    try:
        with urlopen(probe + '/api/catalog', timeout=2) as response:
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
                process = subprocess.Popen([sys.executable, str(ROOT / 'bobtv.py'), '--config', str(config_path.resolve()), 'serve', '--host', host, '--port', str(port)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(40):
            if process is not None and process.poll() is not None:
                raise bobtv.ActionError('Home server could not start; see ~/.local/state/bobtv/home.log')
            try:
                with urlopen(probe + '/api/catalog', timeout=1) as response:
                    if json.load(response).get('app') == 'bobtv': break
            except OSError:
                time.sleep(.1)
        else: raise bobtv.ActionError('Home server did not become ready.')
    if focus_home():
        print('Returned to BobTV home.')
        return 0
    subprocess.Popen(['chromium', '--user-data-dir=' + str(Path.home() / '.local/share/bobtv/home-browser'), '--no-first-run', '--kiosk', probe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    print('Opened BobTV home. Alt+F4 closes the home window.')
    return 0
