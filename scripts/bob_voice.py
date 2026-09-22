"""One bounded push-to-talk session, using the MX3 mic, Whisper and Piper locally."""
import argparse
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bobtv
from smart_home import notify_listening
from voice_control import VOICE_HOME, resolve_service


def emit(phase, message, heard=None):
    data = {'phase': phase, 'message': message}
    if heard is not None:
        data['heard'] = heard
    print(json.dumps(data), flush=True)
    if phase == 'listening':
        notify_listening()


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def source_name():
    result = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'], capture_output=True, text=True, check=True, timeout=5)
    matches = [s['name'] for s in json.loads(result.stdout)
               if 'XING_WEI' in s['name'] and not s['name'].endswith('.monitor')]
    if len(matches) != 1:
        raise RuntimeError('Plug in the MX3 remote receiver. Bob could not find its microphone.')
    return matches[0]


def listen(model, source, seconds=10, prompt='Listening… say “Open BBC”.'):
    from vosk import KaldiRecognizer
    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(True)
    process = subprocess.Popen(['pw-record', '--target', source, '--rate', '16000', '--channels', '1', '--format', 's16', '--raw', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    chunks = []
    try:
        emit('listening', prompt)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not selector.select(.2):
                if process.poll() is not None:
                    raise RuntimeError('The remote microphone disconnected. Try again.')
                continue
            chunk = os.read(process.stdout.fileno(), 4000)
            if not chunk:
                raise RuntimeError('The remote microphone stopped sending audio.')
            chunks.append(chunk)
            if recognizer.AcceptWaveform(chunk):
                result = json.loads(recognizer.Result())
                if result.get('text'):
                    return b"".join(chunks), result
        return b"".join(chunks), json.loads(recognizer.FinalResult())
    finally:
        selector.close()
        stop_process(process)
        process.stdout.close()


def transcribe(model, pcm):
    import numpy as np
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    segments, _ = model.transcribe(audio, language='en', beam_size=5,
        vad_filter=True, condition_on_previous_text=False, word_timestamps=True)
    segments = list(segments)
    text = ' '.join(segment.text.strip() for segment in segments)
    words = [word for segment in segments for word in (segment.words or [])]
    confident = (bool(words) and all(segment.avg_logprob >= -1.0 and segment.no_speech_prob < .6 for segment in segments)
                 and sum(word.probability for word in words) / len(words) >= .55)
    return text, confident


def interpret_audio(result, pcm, services):
    text = result.get('text', '')
    words = result.get('result', [])
    score = sum(w.get('conf', 0) for w in words) / len(words) if words else 0
    service = resolve_service(text, services)
    if service is not None and score >= .8:
        return text, service, False
    from faster_whisper import WhisperModel
    whisper = WhisperModel(str(VOICE_HOME / 'models/faster-whisper-base.en'), device='cpu', compute_type='int8', cpu_threads=2)
    text, confident = transcribe(whisper, pcm)
    return text, resolve_service(text, services), not confident


class Speaker:
    def __init__(self):
        self.voice = None

    def render(self, text, path):
        from speech_cache import audio_name
        folder = VOICE_HOME / 'marin'
        cached = folder / audio_name(text)
        if (folder / 'ready').exists() and cached.exists():
            shutil.copyfile(cached, path)
            return
        if self.voice is None:
            from piper import PiperVoice
            self.voice = PiperVoice.load(str(VOICE_HOME / 'models/en_GB-alan-medium.onnx'))
        with wave.open(str(path), 'wb') as wav:
            self.voice.synthesize_wav(text, wav)

    def say(self, text):
        emit('speaking', text)
        with tempfile.TemporaryDirectory(prefix='bobtv-speech-') as folder:
            path = Path(folder) / 'reply.wav'
            self.render(text, path)
            process = subprocess.Popen(['pw-play', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                if process.wait(timeout=30):
                    raise RuntimeError('Audio playback failed. Check your speaker connection.')
            finally:
                stop_process(process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=ROOT / 'services.json')
    parser.add_argument('--mode', choices=['listen', 'test'], default='listen')
    args = parser.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        config = bobtv.load_config(args.config)
        speaker = Speaker()
        if args.mode == 'test':
            speaker.say('Hello Ken. I am Bob. I am ready to help you find something to watch.')
            emit('done', 'Voice test complete. Did you hear Bob?')
            return 0
        source = source_name()
        from vosk import Model, SetLogLevel
        SetLogLevel(-1)
        model = Model(str(VOICE_HOME / 'models/vosk-model-small-en-us-0.15'))
        speaker.say('What would you like to open?')
        pcm, result = listen(model, source)
        emit('thinking', 'Checking what you said…')
        text, service, uncertain = interpret_audio(result, pcm, config['services'])
        emit('thinking', 'Checking what you said…', text)
        if uncertain and service and service != 'cancel':
            speaker.say('Did you mean ' + config['services'][service]['name'] + '? Say yes or no.')
            _, answer = listen(model, source, prompt='Listening… say yes or no.')
            words = answer.get('result', [])
            certain_yes = (answer.get('text') in {'yes', 'yes please', 'correct'}
                           and words and min(w.get('conf', 0) for w in words) >= .8)
            if not certain_yes:
                emit('done', 'Nothing opened. Try again when you are ready.', answer.get('text', ''))
                return 0

        if service == 'cancel':
            emit('done', 'Cancelled.')
        elif service is None:
            reply = ('I did not catch that. Try saying, open BBC, open Prime, or open Hulu.' if not text
                     else 'I can open streaming services for now. Try saying, open BBC, or open Prime.')
            speaker.say(reply)
            emit('done', reply)
        else:
            name = config['services'][service]['name']
            speaker.say('Opening ' + name + '.')
            emit('opening', 'Opening ' + name + '…')
            state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'bobtv'
            try:
                bobtv.launch(config, service, state)
            except bobtv.ActionError:
                speaker.say('I could not open ' + name + '. Please check the connection and try again.')
                raise
            emit('done', 'Opened ' + name + '.')
        return 0
    except KeyboardInterrupt:
        emit('done', 'Cancelled.')
        return 0
    except Exception as exc:
        emit('error', str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
