"""Run in your own terminal to generate BobTV's fixed replies in Marin once."""
import getpass
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bobtv
from speech_cache import audio_name, generate, phrases
from voice_control import VOICE_HOME


def main():
    folder = VOICE_HOME / 'marin'
    lines = phrases(bobtv.load_config(ROOT / 'services.json')['services'])
    pending = [text for text in lines if not (folder / audio_name(text)).exists()]
    if pending:
        print(f'Generate {len(pending)} short BobTV replies using OpenAI’s Marin voice.')
        print('This uses separately billed OpenAI API access. Only these fixed reply texts are sent.')
        print('Audio is saved locally for reuse; your API key is not saved.')
        answer = input('Generate these replies now? [y/N] ').strip().lower()
        if answer != 'y':
            return
        key = os.environ.get('OPENAI_API_KEY') or getpass.getpass('OpenAI API key (hidden): ').strip()
        if not key:
            raise RuntimeError('No API key entered. The local voice is unchanged.')
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for index, text in enumerate(pending, 1):
            audio = generate(text, key)
            target = folder / audio_name(text)
            temporary = target.with_suffix('.tmp')
            temporary.write_bytes(audio)
            temporary.chmod(0o600)
            temporary.replace(target)
            print(f'Saved {index}/{len(pending)}')
    # Activate only when every required reply is present.
    (folder / 'ready').write_text('marin\n')
    print('Marin is ready. Select Hear Bob on the BobTV home screen.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled. Your current voice remains available.')
    except Exception as exc:
        print(str(exc))
        sys.exit(1)
