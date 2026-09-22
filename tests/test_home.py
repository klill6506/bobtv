import ipaddress
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import bobtv
import home_server

class HomeFocusTests(unittest.TestCase):
    @patch('home_server.subprocess.run')
    def test_reuses_home_without_focusing_stream(self, run):
        run.return_value.stdout = json.dumps([
            {'title': 'Prime Video', 'class': 'chromium', 'address': '0x123'},
            {'title': 'BobTV', 'class': 'chromium', 'address': '0x456'},
        ])
        run.return_value.returncode = 0
        self.assertTrue(home_server.focus_home())
        self.assertIn('address:0x456', run.call_args.args[0][-1])

    @patch('home_server.subprocess.run', side_effect=FileNotFoundError)
    def test_missing_desktop_allows_new_window(self, run):
        self.assertFalse(home_server.focus_home())

class DirectTests(unittest.TestCase):
    def setUp(self):
        self.config = bobtv.load_config(Path('services.json'))

    @patch('bobtv.vpn', side_effect=['Status: Connected\nCountry: United Kingdom', 'Disconnected', 'Status: Disconnected'])
    def test_disconnect_verified(self, vpn):
        bobtv.ensure_region(self.config['regions']['us'])
        self.assertEqual([c.args for c in vpn.call_args_list], [('status',), ('disconnect',), ('status',)])

    @patch('bobtv.vpn', return_value='Status: Disconnected')
    def test_direct_connection_reused(self, vpn):
        bobtv.ensure_region(self.config['regions']['us'])
        vpn.assert_called_once_with('status')

    @patch('bobtv.vpn', side_effect=['Status: Connected\nCountry: United Kingdom', 'Disconnected', 'Status: Disconnected'])
    def test_release_disconnects(self, vpn):
        with tempfile.TemporaryDirectory() as directory:
            bobtv.release(Path(directory))
        self.assertEqual([c.args for c in vpn.call_args_list], [('status',), ('disconnect',), ('status',)])

    @patch('bobtv.vpn', return_value='Status: Disconnected')
    def test_release_when_already_off(self, vpn):
        with tempfile.TemporaryDirectory() as directory:
            bobtv.release(Path(directory))
        vpn.assert_called_once_with('status')

    @patch('bobtv.shutil.which', return_value='tool')
    @patch('bobtv.time.sleep')
    @patch('bobtv.subprocess.Popen')
    @patch('bobtv.vpn', return_value='Status: Connected\nCountry: United Kingdom')
    def test_failed_disconnect_never_launches(self, vpn, browser, sleep, which):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(bobtv.ActionError):
                bobtv.launch(self.config, 'hulu', Path(directory))
        browser.assert_not_called()

class ServerTests(unittest.TestCase):
    def setUp(self):
        with patch('home_server._tailscale_ips', return_value=[]):
            self.server = home_server.make_server(Path('services.json'), port=0)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        with urlopen(self.base + '/api/catalog') as response:
            self.token=json.load(response)['token']

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, service='hulu', origin=None, token=None):
        return urlopen(Request(self.base+'/api/launch', data=json.dumps({'service':service}).encode(), headers={'Origin': origin or self.base, 'X-BobTV-Token':token or self.token}))

    @patch('bobtv.launch')
    def test_cross_origin_blocked(self, launch):
        with self.assertRaises(HTTPError) as error: self.post(origin='https://evil.example')
        self.assertEqual(error.exception.code,403); launch.assert_not_called()

    @patch('bobtv.launch')
    def test_invalid_token_blocked(self, launch):
        with self.assertRaises(HTTPError) as error: self.post(token='invalid')
        self.assertEqual(error.exception.code,403); launch.assert_not_called()

    @patch('bobtv.launch')
    def test_unknown_service_blocked(self, launch):
        with self.assertRaises(HTTPError): self.post(service='https://evil.example')
        launch.assert_not_called()

    @patch('bobtv.launch')
    def test_valid_service_uses_action_layer(self, launch):
        with self.post() as response: self.assertEqual(response.status,200)
        self.assertEqual(launch.call_args.args[1],'hulu')

    def release(self, token=None):
        return urlopen(Request(self.base+'/api/release', data=b'', headers={'Origin': self.base, 'X-BobTV-Token': token or self.token}))

    @patch('bobtv.release')
    def test_release_turns_vpn_off(self, release):
        with self.release() as response: self.assertEqual(response.status,200)
        release.assert_called_once()

    @patch('bobtv.release')
    def test_release_requires_token(self, release):
        with self.assertRaises(HTTPError) as error: self.release(token='invalid')
        self.assertEqual(error.exception.code,403); release.assert_not_called()

    @patch('bobtv.release')
    def test_release_refused_for_remote_clients(self, release):
        tailscale_client = ipaddress.ip_address('100.73.27.12')
        with patch('home_server.ipaddress.ip_address', return_value=tailscale_client):
            with self.assertRaises(HTTPError) as error: self.release()
        self.assertEqual(error.exception.code,403); release.assert_not_called()

    def test_overlapping_launch_rejected(self):
        entered = threading.Event()
        release = threading.Event()
        results = []
        def slow(*args):
            entered.set()
            release.wait(5)
        def first():
            with self.post() as response:
                results.append(response.status)
        with patch('bobtv.launch', side_effect=slow):
            worker = threading.Thread(target=first)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaises(HTTPError) as error: self.post()
                self.assertEqual(error.exception.code, 409)
                error.exception.close()
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(results, [200])

    def test_rebinding_host_blocked(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/catalog', headers={'Host':'evil.example'}))
        self.assertEqual(error.exception.code,403)

    def test_branding_assets_and_private_files(self):
        for route, kind in [('/branding/logo.png', 'image/png'), ('/branding/background.png', 'image/png'), ('/branding/splash.png', 'image/png'), ('/branding/icon.png', 'image/png'), ('/branding/startup.wav', 'audio/wav')]:
            with urlopen(self.base + route) as response:
                self.assertEqual(response.headers['Content-Type'], kind)
                self.assertGreater(len(response.read()), 1000)
        for route in ['/branding/../README.md', '/assets/branding/sound/source/master_take.py']:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + route)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()


class VoiceServerTests(unittest.TestCase):
    setUp = ServerTests.setUp
    tearDown = ServerTests.tearDown
    def voice_post(self, action, origin=None, token=None):
        return urlopen(Request(self.base+'/api/voice/'+action, data=b'', headers={
            'Origin': origin or self.base, 'X-BobTV-Token': token or self.token}))

    def test_voice_post_requires_same_origin_and_token(self):
        with patch.object(self.server.voice, 'start') as start:
            for kwargs in [{'origin': 'https://evil.example'}, {'token': 'wrong'}]:
                with self.assertRaises(HTTPError) as error: self.voice_post('start', **kwargs)
                self.assertEqual(error.exception.code,403)
                error.exception.close()
            start.assert_not_called()

    def test_voice_status_does_not_start_recording(self):
        with patch.object(self.server.voice, 'start') as start:
            with urlopen(self.base+'/api/voice') as response:
                self.assertFalse(json.load(response)['active'])
            start.assert_not_called()

    def test_voice_modes_and_cancel(self):
        for action,mode in [('start','listen'),('test','test')]:
            with patch.object(self.server.voice,'start',return_value={'active':True}) as start:
                with self.voice_post(action) as response: self.assertEqual(response.status,200)
                start.assert_called_once_with(mode)
        with patch.object(self.server.voice,'cancel',return_value={'active':False}) as cancel:
            with self.voice_post('cancel') as response: self.assertEqual(response.status,200)
            cancel.assert_called_once_with()

class RemoteAccessTests(unittest.TestCase):
    setUp = ServerTests.setUp
    tearDown = ServerTests.tearDown
    post = ServerTests.post

    @patch('bobtv.launch')
    def test_other_local_origin_port_and_scheme_rejected(self, launch):
        for origin in ['http://127.0.0.1:1', self.base.replace('http:', 'https:')]:
            with self.assertRaises(HTTPError) as error:
                self.post(origin=origin)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        launch.assert_not_called()

    def test_remote_password_and_unicode(self):
        import base64
        with patch('home_server.ipaddress.ip_address', return_value=ipaddress.ip_address('100.73.27.12')), patch('home_server.PASSWORD', 'café'):
            for password, expected in [(None, 401), ('wrong', 401), ('café', 200)]:
                headers = {} if password is None else {'Authorization': 'Basic ' + base64.b64encode(('bob:' + password).encode()).decode()}
                try:
                    with urlopen(Request(self.base + '/api/catalog', headers=headers)) as response:
                        self.assertEqual(response.status, expected)
                except HTTPError as error:
                    self.assertEqual(error.code, expected)
                    error.close()

    def test_remote_cannot_use_microphone(self):
        with patch('home_server.ipaddress.ip_address', return_value=ipaddress.ip_address('100.73.27.12')), patch.object(self.server.voice, 'start') as start:
            request = Request(self.base + '/api/voice/start', data=b'', headers={'Origin': self.base, 'X-BobTV-Token': self.token})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            start.assert_not_called()

    def test_network_listener_requires_password(self):
        with patch('home_server.PASSWORD', ''), patch('home_server._tailscale_ips', return_value=[]):
            with self.assertRaises(bobtv.ActionError):
                home_server.make_server(Path('services.json'), port=0, host='0.0.0.0')

    def test_extended_startup_audio_is_served(self):
        with urlopen(self.base + '/branding/startup.wav') as response:
            self.assertEqual(response.read(), (home_server.ROOT / 'assets/branding/sound/bobtv-startup-sunrise-v2-long.wav').read_bytes())


class ServeOptionsTests(unittest.TestCase):
    def test_cli_forwards_host_and_port(self):
        with patch('sys.argv', ['bobtv', 'serve', '--host', '0.0.0.0', '--port', '9876']), patch('home_server.run', return_value=0) as run:
            self.assertEqual(bobtv.main(), 0)
            self.assertEqual(run.call_args.kwargs, {'host': '0.0.0.0', 'port': 9876})
