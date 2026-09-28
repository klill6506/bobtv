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

HOME_PID, SHOW_PID = 111, 222


class HomeFocusTests(unittest.TestCase):
    """The home window is found by its browser profile, not its title."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.windows = {}
        self.log = []
        for name, value in (('clients', lambda: {a: dict(w) for a, w in self.windows.items()}),
                            ('focus', lambda a: self.log.append(('focus', a))),
                            ('close', lambda a: (self.log.append(('close', a)), self.windows.pop(a, None))),
                            ('make_fullscreen', lambda: self.log.append(('fullscreen',)))):
            patcher = patch('windows.' + name, side_effect=value)
            self.addCleanup(patcher.stop)
            patcher.start()
        profile = patch('home_server.is_home_browser', side_effect=lambda pid: pid == HOME_PID)
        self.addCleanup(profile.stop)
        profile.start()

    def window(self, address, title, pid, fullscreen=0):
        self.windows[address] = {'address': address, 'title': title, 'class': 'chromium',
                                 'pid': pid, 'fullscreen': fullscreen}

    def test_reuses_home_without_focusing_stream(self):
        self.window('0x123', 'Prime Video', SHOW_PID)
        self.window('0x456', 'BobTV', HOME_PID)
        self.assertTrue(home_server.focus_home(self.state))
        self.assertIn(('focus', '0x456'), self.log)
        self.assertNotIn(('focus', '0x123'), self.log)
        self.assertNotIn(('close', '0x123'), self.log, 'focus_home never closes a show')

    def test_home_is_made_fullscreen(self):
        self.window('0x456', 'BobTV', HOME_PID, fullscreen=0)
        home_server.focus_home(self.state)
        self.assertIn(('fullscreen',), self.log)

    def test_duplicate_home_windows_are_closed(self):
        self.window('0x456', 'BobTV', HOME_PID)
        self.window('0x789', 'BobTV Smart Home – Home Assistant - Chromium', HOME_PID)
        self.window('0x999', 'BobTV', HOME_PID)
        self.assertTrue(home_server.focus_home(self.state))
        self.assertEqual(sorted(entry[1] for entry in self.log if entry[0] == 'close'), ['0x789', '0x999'])
        self.assertIn('0x456', self.windows)

    def test_a_home_window_on_home_assistant_needs_a_fresh_home(self):
        self.window('0x789', 'BobTV Smart Home – Home Assistant - Chromium', HOME_PID)
        self.assertFalse(home_server.focus_home(self.state))
        self.assertNotIn(('close', '0x789'), self.log, 'never close the last window of the browser')

    def test_the_doorbell_camera_is_not_mistaken_for_home(self):
        self.window('0x456', 'BobTV', HOME_PID)
        self.window('0xcafe', 'BobTV', HOME_PID)
        (self.state / 'doorbell-window').write_text('0xcafe')
        home_server.focus_home(self.state)
        self.assertNotIn(('close', '0xcafe'), self.log)

    def test_missing_desktop_allows_new_window(self):
        with patch('windows.clients', side_effect=bobtv.ActionError('no desktop')):
            self.assertFalse(home_server.focus_home(self.state))


class ProfileTests(unittest.TestCase):
    def test_the_home_profile_is_recognised_from_the_command_line(self):
        args = b'\0'.join([b'/usr/lib/chromium/chromium', b'--user-data-dir=' + home_server.HOME_PROFILE.encode(), b'--kiosk'])
        with patch('home_server.Path.read_bytes', return_value=args):
            self.assertTrue(home_server.is_home_browser(19680))
        with patch('home_server.Path.read_bytes', return_value=b'/usr/lib/chromium/chromium\0--new-window'):
            self.assertFalse(home_server.is_home_browser(45379))

    def test_a_missing_or_bad_pid_is_not_home(self):
        self.assertFalse(home_server.is_home_browser(None))
        self.assertFalse(home_server.is_home_browser('x'))
        self.assertFalse(home_server.is_home_browser(2 ** 30))


class HomeButtonTests(unittest.TestCase):
    """Home means stop watching: the show and the doorbell camera close."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)

    @patch('home_server.focus_home', return_value=True)
    @patch('home_server.urlopen')
    def test_home_closes_the_show_and_the_camera(self, urlopen_, focus):
        urlopen_.return_value.__enter__.return_value.read.return_value = b'{"app": "bobtv"}'
        with patch('home_server.json.load', return_value={'app': 'bobtv'}), \
             patch('home_server._state_dir', return_value=self.state), \
             patch('bobtv.close_show') as close_show, \
             patch('windows.close_remembered') as close_camera:
            self.assertEqual(home_server.run('home', Path('services.json')), 0)
        close_show.assert_called_once_with(self.state)
        self.assertEqual(close_camera.call_args.args[0], self.state / 'doorbell-window')
        focus.assert_called_once_with(self.state)

class DirectTests(unittest.TestCase):
    def setUp(self):
        self.config = bobtv.load_config(Path('services.json'))
        # TV control also spawns a process; hold it still so the Popen mock in
        # these tests still means "the browser". tests/test_tv.py covers the TV.
        wake = patch('bobtv.tv_wake')
        self.addCleanup(wake.stop)
        wake.start()
        for target in ('bobtv.window_snapshot', 'bobtv.close_show'):
            patcher = patch(target, return_value=None)
            self.addCleanup(patcher.stop)
            patcher.start()

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
