import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import voice_control
from voice_control import VoiceController, resolve_service

SERVICES = json.loads(Path('services.json').read_text())['services']


class IntentTests(unittest.TestCase):
    def test_services_and_polite_prefixes(self):
        for text, expected in [('Open BBC', 'bbc-iplayer'), ('Hey Bob, please open Prime.', 'prime-video'),
                               ('put on YouTube TV please', 'youtube-tv'), ('open you tube', 'youtube'),
                               ('Bob TV open Hulu', 'hulu'), ('open apple t v', 'apple-tv')]:
            with self.subTest(text=text):
                self.assertEqual(resolve_service(text, SERVICES), expected)

    def test_no_guessing_titles_negation_or_multiple_targets(self):
        for text in ['do not open BBC', 'open BBC or Prime', 'open Grantchester',
                     'open prime tomorrow', 'I was watching BBC', '', 'open bbc; reboot',
                     'open https://evil.example', 'please do not open hulu']:
            with self.subTest(text=text):
                self.assertIsNone(resolve_service(text, SERVICES))

    def test_cancel_and_missing_service(self):
        self.assertEqual(resolve_service('Bob cancel', SERVICES), 'cancel')
        self.assertIsNone(resolve_service('open BBC', {}))


class SupervisorTests(unittest.TestCase):
    def test_launch_busy_prevents_microphone_process(self):
        busy=threading.Lock();busy.acquire()
        controller=VoiceController(Path('services.json'), busy)
        with patch('voice_control.subprocess.Popen') as spawn:
            with self.assertRaises(RuntimeError): controller.start()
            spawn.assert_not_called()
        busy.release()

    def test_missing_install_releases_lock(self):
        busy=threading.Lock()
        with tempfile.TemporaryDirectory() as folder, patch('voice_control.VOICE_HOME',Path(folder)):
            with self.assertRaises(RuntimeError): VoiceController(Path('services.json'),busy).start()
        self.assertFalse(busy.locked())

    def test_cancel_stops_process_and_releases_lock(self):
        real_popen=subprocess.Popen
        def child(*args, **kwargs):
            return real_popen([sys.executable,'-c','import time; time.sleep(30)'], **kwargs)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'venv/bin').mkdir(parents=True);(root/'venv/bin/python').touch()
            busy=threading.Lock();controller=VoiceController(Path('services.json'),busy)
            with patch('voice_control.VOICE_HOME',root), patch('voice_control.subprocess.Popen',side_effect=child):
                controller.start()
                self.assertTrue(controller.status()['active'])
                controller.cancel()
                limit=time.monotonic()+3
                while controller.status()['active'] and time.monotonic()<limit: time.sleep(.02)
            self.assertFalse(controller.status()['active'])
            self.assertFalse(busy.locked())
            self.assertEqual(controller.status()['message'],'Cancelled.')

class MarinTests(unittest.TestCase):
    def test_request_selects_marin_and_wav(self):
        import io
        import speech_cache
        audio = b'RIFF' + b'\0' * 4 + b'WAVE' + b'test'
        with patch('speech_cache.urlopen',return_value=io.BytesIO(audio)) as request:
            self.assertEqual(speech_cache.generate('Hello Ken.', 'test-key'),audio)
        payload=json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['voice'],'marin')
        self.assertEqual(payload['model'],'gpt-4o-mini-tts')
        self.assertEqual(payload['response_format'],'wav')
        self.assertEqual(payload['input'],'Hello Ken.')

    def test_invalid_audio_never_cached(self):
        import io
        import speech_cache
        with patch('speech_cache.urlopen',return_value=io.BytesIO(b'not audio')):
            with self.assertRaises(RuntimeError):speech_cache.generate('Hello', 'test-key')

    def test_cached_reply_does_not_need_piper_or_api(self):
        from scripts.bob_voice import Speaker
        from speech_cache import audio_name
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'marin';cache.mkdir()
            (cache/'ready').touch();(cache/audio_name('Hello')).write_bytes(b'cached-wav')
            with patch('scripts.bob_voice.VOICE_HOME',root):
                speaker=Speaker();speaker.render('Hello',root/'reply.wav')
                self.assertIsNone(speaker.voice)
                self.assertEqual((root/'reply.wav').read_bytes(),b'cached-wav')


class VoiceExecutionTests(unittest.TestCase):
    def run_uncertain(self, answer):
        from types import SimpleNamespace
        from scripts import bob_voice
        fake=SimpleNamespace(Model=lambda _:object(),SetLogLevel=lambda _:None)
        with patch.dict(sys.modules,{'vosk':fake}), patch('sys.argv',['bob_voice']), \
             patch.object(bob_voice,'Speaker'), patch.object(bob_voice,'source_name',return_value='remote'), \
             patch.object(bob_voice,'listen',side_effect=[(b'a',{}),(b'b',answer)]), \
             patch.object(bob_voice,'interpret_audio',return_value=('Open Houlou.', 'hulu', True)), \
             patch.object(bob_voice,'emit'), patch.object(bob_voice.signal,'signal'), \
             patch.object(bob_voice.bobtv,'launch') as launch:
            result=bob_voice.main()
            return result,launch.call_args_list

    def test_uncertain_command_does_not_launch_without_yes(self):
        for answer in [{'text':'no'}, {'text':''}, {'text':'yes','result':[{'conf':.3}]}]:
            result,calls=self.run_uncertain(answer)
            self.assertEqual(result,0);self.assertEqual(calls,[])

    def test_uncertain_command_launches_after_confident_yes(self):
        result,calls=self.run_uncertain({'text':'yes','result':[{'conf':.99}]})
        self.assertEqual(result,0);self.assertEqual(len(calls),1)
        self.assertEqual(calls[0].args[1],'hulu')
