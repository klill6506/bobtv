"""Read-only adapter for Ken's existing What’sOn tracker."""
import json
import threading
import time
from urllib.request import urlopen
from urllib.parse import urlparse

URL = 'https://whatson.kenlill.com/api/shows'
SERVICE_IDS = {'Netflix':'netflix', 'Apple TV+':'apple-tv', 'Apple TV':'apple-tv', 'Max':'hbo-max', 'HBO Max':'hbo-max', 'Hulu':'hulu', 'Paramount+':'paramount-plus', 'Peacock':'peacock', 'Prime Video':'prime-video', 'BBC iPlayer':'bbc-iplayer', 'ITVX':'itvx', 'Channel 4':'channel4'}
_lock = threading.Lock()
_cache = None
_updated = 0


def normalize(rows):
    if not isinstance(rows, list):
        raise ValueError('Invalid show list')
    result = []
    for row in rows:
        if row.get('status') != 'watching' or row.get('current_episode') == 99:
            continue
        poster = row.get('poster_url') or ''
        url = urlparse(poster)
        if url.scheme != 'https' or url.hostname != 'image.tmdb.org':
            poster = ''
        result.append({'title': str(row.get('title', 'Untitled')), 'service': str(row.get('service', '')), 'service_id': SERVICE_IDS.get(row.get('service')), 'season': row.get('current_season'), 'episode': row.get('current_episode'), 'poster': poster})
    return result


def shows():
    global _cache, _updated
    with _lock:
        if _cache is not None and time.monotonic() - _updated < 300:
            return {'shows': _cache, 'stale': False}
        try:
            with urlopen(URL, timeout=8) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Show list too large')
            _cache = normalize(json.loads(raw))
            _updated = time.monotonic()
            return {'shows': _cache, 'stale': False}
        except Exception:
            if _cache is not None:
                return {'shows': _cache, 'stale': True}
            raise ValueError('What’sOn is unavailable. Your streaming services still work.') from None
