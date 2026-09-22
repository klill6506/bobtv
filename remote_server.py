"""Paired LAN button remote; the main home server stays loopback-only."""
import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import secrets
from socketserver import TCPServer
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bobtv
import home_server

ROOT = Path(__file__).resolve().parent
COMMANDS = {
    'play-pause': ['omarchy-shell', 'media', 'playPause'],
    'volume-up': ['omarchy-audio-output-volume', 'raise'],
    'volume-down': ['omarchy-audio-output-volume', 'lower'],
    'mute': ['omarchy-audio-output-volume', 'mute-toggle'],
}


def pairing_token(state):
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = state / 'remote-token'
    # Lock before reading: service startup and printing a pairing link may race.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'r+') as output:
        fcntl.flock(output, fcntl.LOCK_EX)
        token = output.read().strip()
        if len(token) < 32:
            token = secrets.token_urlsafe(32)
            output.seek(0)
            output.write(token)
            output.truncate()
            output.flush()
        return token


class RemoteHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer otherwise performs reverse DNS, which can stall on a LAN.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address



def make_server(host, port, token, config_path, state):
    if len(token) < 32:
        raise ValueError('A strong pairing token is required')
    busy = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, code, data, kind='application/json'):
            body = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            if self.headers.get('Host') != f'{host}:{self.server.server_port}':
                self.reply(403, {'error': 'Invalid host'})
                return False
            return True

        def authorized(self):
            if not secrets.compare_digest(self.headers.get('X-BobTV-Token', ''), token):
                self.reply(403, {'error': 'Open your private pairing link to connect.'})
                return False
            return True

        def do_GET(self):
            if not self.valid_host():
                return
            if self.path == '/api/catalog':
                if not self.authorized():
                    return
                try:
                    services = bobtv.load_config(config_path)['services']
                    self.reply(200, {'services': {key: {'name': value['name'], 'region': value['region']} for key, value in services.items()}})
                except bobtv.ActionError as exc:
                    self.reply(503, {'error': str(exc)})
                return
            files = {'/': ('remote.html', 'text/html; charset=utf-8'), '/remote.js': ('remote.js', 'text/javascript'), '/remote.css': ('remote.css', 'text/css')}
            if self.path not in files:
                self.reply(404, {'error': 'Not found'})
                return
            name, kind = files[self.path]
            self.reply(200, (ROOT / 'web' / name).read_bytes(), kind)

        def do_POST(self):
            if not self.valid_host() or not self.authorized():
                return
            if self.headers.get('Origin') != f'http://{host}:{self.server.server_port}':
                self.reply(403, {'error': 'Untrusted origin'})
                return
            if self.path != '/api/action':
                self.reply(404, {'error': 'Not found'})
                return
            if not busy.acquire(blocking=False):
                self.reply(409, {'error': 'Please wait for the previous button.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                action = data.get('action')
                if action == 'launch':
                    service = data.get('service')
                    config = bobtv.load_config(config_path)
                    if not isinstance(service, str) or service not in config['services']:
                        raise ValueError('Unknown channel')
                    bobtv.launch(config, service, state)
                    message = 'Opened ' + config['services'][service]['name']
                elif action == 'home':
                    home_server.run('home', config_path)
                    message = 'Home opened on TV'
                elif isinstance(action, str) and action in COMMANDS:
                    subprocess.run(COMMANDS[action], capture_output=True, text=True, check=True, timeout=10)
                    message = 'Sent to TV'
                else:
                    raise ValueError('Unknown button')
                self.reply(200, {'message': message})
            except (ValueError, AttributeError, OSError, bobtv.ActionError, subprocess.SubprocessError) as exc:
                self.reply(400, {'error': str(exc)})
            finally:
                busy.release()

    server = RemoteHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--url', action='store_true', help='Print the private pairing link')
    args = parser.parse_args()
    address = ipaddress.IPv4Address(args.host)
    if not any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        parser.error('Use the computer’s private LAN IPv4 address')
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'bobtv'
    token = pairing_token(state)
    if args.url:
        print(f'http://{args.host}:{args.port}/#' + token)
        return
    make_server(args.host, args.port, token, ROOT / 'services.json', state).serve_forever()


if __name__ == '__main__':
    main()
