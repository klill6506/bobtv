import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import remote_server


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token = 'a' * 43
        self.server = remote_server.make_server('127.0.0.1', 0, self.token, remote_server.ROOT / 'services.json', Path(self.tmp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, data=None, token=None, origin=None, host=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        headers = {'Host': host or f'127.0.0.1:{self.port}'}
        if token is not None:
            headers['X-BobTV-Token'] = token
        if origin is not None:
            headers['Origin'] = origin
        conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_catalog_requires_pairing_and_never_exposes_token(self):
        self.assertEqual(self.request('/api/catalog')[0], 403)
        status, body = self.request('/api/catalog', token=self.token)
        self.assertEqual(status, 200)
        self.assertIn('services', json.loads(body))
        self.assertNotIn(self.token.encode(), body)

    def test_rejects_untrusted_host_origin_and_unknown_action(self):
        self.assertEqual(self.request('/', host='evil.example')[0], 403)
        with patch('remote_server.subprocess.run') as run:
            self.assertEqual(self.request('/api/action', {'action': 'mute'}, token=self.token, origin='http://evil.example')[0], 403)
            self.assertEqual(self.request('/api/action', {'action': 'mute'}, origin=f'http://127.0.0.1:{self.port}')[0], 403)
            self.assertEqual(self.request('/api/action', {'action': 'shell'}, token=self.token, origin=f'http://127.0.0.1:{self.port}')[0], 400)
            run.assert_not_called()

    def test_buttons_use_allowlisted_commands(self):
        with patch('remote_server.subprocess.run') as run:
            status, _ = self.request('/api/action', {'action': 'mute'}, token=self.token, origin=f'http://127.0.0.1:{self.port}')
            self.assertEqual(status, 200)
            self.assertEqual(run.call_args.args[0], ['omarchy-audio-output-volume', 'mute-toggle'])

    def test_launch_validates_service_and_uses_shared_actions(self):
        with patch('remote_server.bobtv.launch') as launch:
            origin = f'http://127.0.0.1:{self.port}'
            self.assertEqual(self.request('/api/action', {'action': 'launch', 'service': 'bad'}, token=self.token, origin=origin)[0], 400)
            launch.assert_not_called()
            service = next(iter(remote_server.bobtv.load_config(remote_server.ROOT / 'services.json')['services']))
            self.assertEqual(self.request('/api/action', {'action': 'launch', 'service': service}, token=self.token, origin=origin)[0], 200)
            self.assertEqual(launch.call_args.args[1], service)

    def test_only_remote_assets_public(self):
        for path in ('/', '/remote.css', '/remote.js'):
            status, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertNotIn(self.token.encode(), body)
        for path in ('/api/voice', '/api/status', '/../services.json'):
            self.assertEqual(self.request(path)[0], 404)

    def test_pairing_persists_with_private_permissions(self):
        state = Path(self.tmp.name)
        token = remote_server.pairing_token(state)
        self.assertEqual(remote_server.pairing_token(state), token)
        self.assertEqual((state / 'remote-token').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
