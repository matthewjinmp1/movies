"""Validated, atomic storage for the personal filter settings."""
import json
import math
import os
import tempfile
import threading
from pathlib import Path
import score_settings

PATH = Path(__file__).resolve().parent / 'filters.json'
LOCK = threading.Lock()
KEYS = {'genres','averageRating','numVotes','startYear','runtimeMinutes','isAdult'}

def validate(data):
    if not isinstance(data,dict) or data.get('version') != 1:
        raise ValueError('Invalid filter settings format.')
    if not isinstance(data.get('q'),str) or len(data['q'])>500:
        raise ValueError('Search must be at most 500 characters.')
    visible=data.get('visibleFilters')
    if not isinstance(visible,list) or len(visible)>6 or any(not isinstance(k,str) or k not in KEYS for k in visible) or len(set(visible))!=len(visible):
        raise ValueError('Invalid visible filters.')
    values=data.get('values')
    if not isinstance(values,dict) or set(values)!=KEYS:
        raise ValueError('Invalid filter values.')
    for key,v in values.items():
        if not isinstance(v,dict): raise ValueError('Invalid filter value.')
        if key=='genres':
            genres=v.get('values')
            if v.get('mode') not in ('any_of','all_of') or not isinstance(genres,list) or len(genres)>30 or any(not isinstance(g,str) or not g or len(g)>50 or ',' in g for g in genres):
                raise ValueError('Invalid genre choices.')
        elif key=='isAdult':
            if v.get('value') not in ('','0','1'): raise ValueError('Invalid adult content choice.')
        else:
            if key=='averageRating' and v.get('status') not in ('any','rated','unrated'):
                raise ValueError('Invalid rating availability.')
            for part in (('min','max') if key in ('startYear','runtimeMinutes') else ('min',)):
                n=v.get(part)
                if not isinstance(n,str) or len(n)>30: raise ValueError('Invalid numeric filter.')
                if n and (not math.isfinite(float(n)) or float(n)<0): raise ValueError('Invalid numeric filter.')
            if v.get('min') and v.get('max') and float(v['min'])>float(v['max']):
                raise ValueError('Minimum cannot exceed maximum.')
    result={k:data[k] for k in ('version','q','visibleFilters','values')}
    if 'scoring' in data: result['scoring']=score_settings.validate(data['scoring'])
    return result

def read(path=PATH):
    with LOCK:
        if not path.exists(): return None
        return validate(json.loads(path.read_text(encoding='utf-8')))

def save(data,path=PATH):
    data=validate(data)
    with LOCK:
        name=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
                name=f.name
                json.dump(data,f,indent=2,ensure_ascii=False)
                f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if name and os.path.exists(name): os.unlink(name)
    return data
