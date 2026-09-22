import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import smart_home


class CueTests(unittest.TestCase):
    def test_fixed_loopback_destination_no_proxy_and_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps({'listening_webhook_id': 'a' * 43}))
            response = MagicMock()
            response.__enter__.return_value.status = 200
            with patch('smart_home.build_opener') as opener:
                opener.return_value.open.return_value = response
                self.assertTrue(smart_home.send_listening_cue(config))
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url, 'http://127.0.0.1:8123/api/webhook/' + 'a' * 43)
                self.assertEqual(request.get_method(), 'POST')
                self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 1)
                self.assertEqual(opener.call_args.args[0].proxies, {})

    def test_missing_config_and_invalid_hook_do_not_send(self):
        with tempfile.TemporaryDirectory() as folder, patch('smart_home.build_opener') as opener:
            config = Path(folder) / 'config.json'
            self.assertFalse(smart_home.send_listening_cue(config))
            config.write_text(json.dumps({'listening_webhook_id': '../other'}))
            self.assertFalse(smart_home.send_listening_cue(config))
            opener.assert_not_called()

    def test_slow_cue_does_not_block_or_overlap(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def slow():
            started.set()
            release.wait(3)
            finished.set()
        with patch('smart_home.send_listening_cue', side_effect=slow) as send:
            try:
                smart_home.notify_listening()
                self.assertTrue(started.wait(1))
                smart_home.notify_listening()
                self.assertEqual(send.call_count, 1)
            finally:
                release.set()
                self.assertTrue(finished.wait(1))

    def test_only_listening_emits_cue(self):
        from scripts import bob_voice
        with patch.object(bob_voice, 'notify_listening') as notify, patch('sys.stdout', new_callable=io.StringIO):
            for phase in ['starting', 'speaking', 'thinking', 'done', 'error']:
                bob_voice.emit(phase, 'test')
            notify.assert_not_called()
            bob_voice.emit('listening', 'Ready')
            notify.assert_called_once_with()
