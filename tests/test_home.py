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
