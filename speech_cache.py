"""Optional pre-generated Marin replies. No API key is kept by BobTV."""
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = 'gpt-4o-mini-tts'
VOICE = 'marin'
INSTRUCTIONS = 'Speak warmly and naturally, with clear, concise delivery. You are Bob, a helpful television companion.'


def audio_name(text):
    data = json.dumps([MODEL, VOICE, INSTRUCTIONS, text]).encode()
    return hashlib.sha256(data).hexdigest() + '.wav'


def phrases(services):
    replies = [
        'Hello Ken. I am Bob. I am ready to help you find something to watch.',
        'What would you like to open?',
        'I did not catch that. Try saying, open BBC, open Prime, or open Hulu.',
        'I can open streaming services for now. Try saying, open BBC, or open Prime.',
    ]
    for service in services.values():
        replies.extend(['Opening ' + service['name'] + '.',
                        'Did you mean ' + service['name'] + '? Say yes or no.',
                        'I could not open ' + service['name'] + '. Please check the connection and try again.'])
    return list(dict.fromkeys(replies))


def generate(text, key):
    if not key or not key.isascii() or any(char.isspace() for char in key):
        raise RuntimeError('The API key contains invalid characters. Copy it again.')
    payload = json.dumps({'model': MODEL, 'voice': VOICE, 'input': text,
                          'instructions': INSTRUCTIONS, 'response_format': 'wav'}).encode()
    request = Request('https://api.openai.com/v1/audio/speech', data=payload,
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=60) as response:
            audio = response.read(8 * 1024 * 1024 + 1)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise RuntimeError(f'OpenAI speech request failed (HTTP {code}). Check API access and billing.') from None
    except (URLError, TimeoutError):
        raise RuntimeError('Could not reach OpenAI. No automatic retry was made.') from None
    if len(audio) > 8 * 1024 * 1024 or not (audio[:4] == b'RIFF' and audio[8:12] == b'WAVE'):
        raise RuntimeError('OpenAI did not return a valid WAV response.')
    return audio
