"""Validated, atomic storage for the personal filter settings."""
import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path
import score_settings
import enrichment

PATH = Path(__file__).resolve().parent / 'filters.json'
# Every saved version is also appended here (one file per tab), so a lost filter can be brought back.
HISTORY_KEEP = 500
LOCK = threading.Lock()
KEYS = {'genres','averageRating','numVotes','startYear','runtimeMinutes','isAdult'}

def validate(data):
    if not isinstance(data,dict) or data.get('version') != 1:
        raise ValueError('Invalid filter settings format.')
    if not isinstance(data.get('q'),str) or len(data['q'])>500:
        raise ValueError('Search must be at most 500 characters.')
    visible=data.get('visibleFilters')
    if not isinstance(visible,list) or len(visible)>7+len(enrichment.BY_KEY) or any(not isinstance(k,str) or k not in KEYS | {'notSeen'} | set(enrichment.BY_KEY) for k in visible) or len(set(visible))!=len(visible):
        raise ValueError('Invalid visible filters.')
    values=data.get('values')
    if not isinstance(values,dict) or not KEYS <= set(values) or set(values) - KEYS - {'notSeen'} - set(enrichment.BY_KEY):
        raise ValueError('Invalid filter values.')
    for key,v in values.items():
        if not isinstance(v,dict): raise ValueError('Invalid filter value.')
        if key in enrichment.CATEGORIES:
            if v.get('mode') not in ('any_of','all_of') or not isinstance(v.get('values'),list) or len(v['values'])>100 or any(not isinstance(x,str) or len(x)>300 for x in v['values']):raise ValueError('Invalid category choices.')
        elif key in enrichment.NUMERIC:
            if v.get('status') not in ('any','present','missing'):raise ValueError('Invalid availability choice.')
            for part in ('min','max'):
                n=v.get(part)
                if not isinstance(n,str) or (n and (not math.isfinite(float(n)) or float(n)<0)):raise ValueError('Invalid numeric filter.')
            if v.get('min') and v.get('max') and float(v['min'])>float(v['max']):raise ValueError('Minimum cannot exceed maximum.')
        elif key=='mdbAvailable':
            if v.get('value') not in ('','0','1'):raise ValueError('Invalid data availability.')
        elif key=='notSeen':
            if v != {}: raise ValueError('Invalid not seen choice.')
        elif key=='genres':
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

def view_path(view='all'):
    if view not in ('all','starred','seen','blocked'):
        raise ValueError('Invalid movie view.')
    return PATH if view=='all' else PATH.with_name(f'filters_{view}.json')

class Conflict(Exception):
    """The settings were changed elsewhere (another window) since this copy was loaded."""
    def __init__(self,current,rev):
        super().__init__('Filters were changed in another window.')
        self.current,self.rev=current,rev

def _rev(raw):
    rev=raw.get('rev') if isinstance(raw,dict) else None
    return rev if isinstance(rev,int) and rev>=0 else 0

def read(path=PATH):
    with LOCK:
        if not path.exists(): return None
        return validate(json.loads(path.read_text(encoding='utf-8')))

def read_rev(path=PATH):
    """The settings and their revision (bumped on every save; 0 if never saved with one)."""
    with LOCK:
        if not path.exists(): return None,0
        raw=json.loads(path.read_text(encoding='utf-8'))
        return validate(raw),_rev(raw)

def history_path(path):
    return path.parent/'filter_history'/(path.stem+'.jsonl')

def _append_history(path,raw):
    hist=history_path(path)
    hist.parent.mkdir(exist_ok=True)
    lines=hist.read_text(encoding='utf-8').splitlines() if hist.exists() else []
    lines.append(json.dumps(raw,ensure_ascii=False,separators=(',',':')))
    hist.write_text('\n'.join(lines[-HISTORY_KEEP:])+'\n',encoding='utf-8')

def save(data,path=PATH,base_rev=None):
    """Save the settings. With base_rev, refuse (Conflict) if the saved copy has moved on since that
    revision, so a stale window can't overwrite newer filters. Returns the new revision."""
    data=validate(data)
    with LOCK:
        current,rev=None,0
        if path.exists():
            try:
                raw=json.loads(path.read_text(encoding='utf-8'))
                current,rev=validate(raw),_rev(raw)
            except (ValueError,TypeError,KeyError):
                current=None
        if base_rev is not None and current is not None and base_rev!=rev:
            raise Conflict(current,rev)
        if current==data: return rev
        rev+=1
        data={**data,'rev':rev,'savedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}
        _append_history(path,data)
        name=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
                name=f.name
                json.dump(data,f,indent=2,ensure_ascii=False)
                f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if name and os.path.exists(name): os.unlink(name)
    return rev
