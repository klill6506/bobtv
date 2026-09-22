"""A bounded, local-only listening cue; no Home Assistant account token needed."""
import json
import logging
from pathlib import Path
import re
import threading
from urllib.request import Request, ProxyHandler, build_opener

CONFIG = Path.home() / '.config/bobtv/smart-home.json'
_pending = threading.Lock()
_log = logging.getLogger(__name__)


def send_listening_cue(config_path=CONFIG):
    """Send one short flash request. Never retry or expose the private URL."""
    try:
        config = json.loads(Path(config_path).read_text())
        hook = config.get('listening_webhook_id', '')
        if not isinstance(hook, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', hook):
            return False
        request = Request('http://127.0.0.1:8123/api/webhook/' + hook, data=b'', method='POST')
        # Local control must never travel through an HTTP proxy.
        with build_opener(ProxyHandler({})).open(request, timeout=1) as response:
            return 200 <= response.status < 300
    except (OSError, ValueError, TypeError, AttributeError):
        _log.warning('BobTV listening light cue unavailable; voice continues.')
        return False


def notify_listening():
    """Do not delay microphone capture if Home Assistant is slow or offline."""
    if not _pending.acquire(blocking=False):
        return

    def run():
        try:
            send_listening_cue()
        finally:
            _pending.release()

    try:
        threading.Thread(target=run, daemon=True).start()
    except RuntimeError:
        _pending.release()
