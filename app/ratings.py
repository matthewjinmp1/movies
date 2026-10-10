"""Atomic local storage for personal 0–100 movie ratings."""
import json
import math
import os
import re
import tempfile
import threading
from pathlib import Path

PATH = Path(__file__).resolve().parent / 'ratings.json'
LOCK = threading.RLock()


def valid(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100


def read(path=None):
    path = path or PATH
    with LOCK:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or any(not re.fullmatch(r'tt[0-9]+', k) or not valid(v) for k, v in data.items()):
            raise ValueError('Invalid movie ratings.')
        return data


def update(movie_id, rating, path=None):
    """Set a rating, or remove it when rating is None. Ratings keep one decimal place."""
    path = path or PATH
    if not isinstance(movie_id, str) or not re.fullmatch(r'tt[0-9]+', movie_id) or not (rating is None or valid(rating)):
        raise ValueError('Enter a rating from 0 to 100.')
    with LOCK:
        data = read(path)
        if rating is None:
            data.pop(movie_id, None)
        else:
            data[movie_id] = round(float(rating), 1)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
                name = f.name
                json.dump(dict(sorted(data.items())), f, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        return len(data)
