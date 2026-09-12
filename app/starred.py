"""Atomic local storage for saved movie IDs."""
import json
import os
import re
import tempfile
import threading
from pathlib import Path

PATH = Path(__file__).resolve().parent / 'starred.json'
LOCK = threading.RLock()

def read(path=None):
    path = path or PATH
    with LOCK:
        if not path.exists(): return set()
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list) or any(not isinstance(v,str) or not re.fullmatch(r'tt[0-9]+',v) for v in data):
            raise ValueError('Invalid starred movie list.')
        return set(data)

def update(movie_id, selected, path=None):
    path = path or PATH
    if not isinstance(movie_id,str) or not re.fullmatch(r'tt[0-9]+',movie_id) or type(selected) is not bool:
        raise ValueError('Invalid starred movie selection.')
    with LOCK:
        ids = read(path)
        if selected: ids.add(movie_id)
        else: ids.discard(movie_id)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
                name = f.name
                json.dump(sorted(ids),f,indent=2)
                f.write('\n'); f.flush(); os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if name and os.path.exists(name): os.unlink(name)
        return len(ids)
