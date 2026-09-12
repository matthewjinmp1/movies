"""Library-wide preference scores, independent of search and filters."""
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
from collections import Counter
from contextlib import closing
from pathlib import Path
from score_settings import number

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'global_scoring.json'
LOCK = threading.RLock()
LABELS = {'genres':'Genres','averageRating':'IMDb rating','numVotes':'Vote count','startYear':'Release year','runtimeMinutes':'Runtime','isAdult':'Adult content'}
NUMERIC = ['averageRating','numVotes','startYear','runtimeMinutes']
DEFAULTS = {
    'weights':dict(zip(LABELS,[1,3,1,1,0,0])),
    'genrePoints':{}, 'genreMode':'percentile', 'missingScore':0,
    'adultScores':{'0':100,'1':0},
    'fields':{key:dict(mode='target' if key=='runtimeMinutes' else 'higher',scale='percentile',low=lo,high=hi,target=target,tolerance=tolerance)
              for key,lo,hi,target,tolerance in [('averageRating',0,10,8,2),('numVotes',0,1000000,100000,100000),('startYear',1900,2026,2000,25),('runtimeMinutes',60,180,120,60)]},
}

def validate(data=None):
    result=copy.deepcopy(DEFAULTS)
    if data is None: return result
    if not isinstance(data,dict) or set(data)!=set(result): raise ValueError('Invalid global scoring settings.')
    if not isinstance(data['weights'],dict) or set(data['weights'])!=set(LABELS): raise ValueError('Invalid global weights.')
    for value in data['weights'].values(): number(value,0,10)
    if not isinstance(data['genrePoints'],dict) or len(data['genrePoints'])>50: raise ValueError('Invalid genre points.')
    for genre,value in data['genrePoints'].items():
        if not isinstance(genre,str) or not genre or len(genre)>50 or ',' in genre: raise ValueError('Invalid genre.')
        number(value,-10,10)
    if data['genreMode'] not in ('percentile','fixed'): raise ValueError('Invalid genre scale.')
    number(data['missingScore'],0,100)
    if not isinstance(data['adultScores'],dict) or set(data['adultScores'])!={'0','1'}: raise ValueError('Invalid adult scores.')
    for value in data['adultScores'].values(): number(value,0,100)
    if not isinstance(data['fields'],dict) or set(data['fields'])!=set(NUMERIC): raise ValueError('Invalid global fields.')
    for key,v in data['fields'].items():
        if not isinstance(v,dict) or set(v)!={'mode','scale','low','high','target','tolerance'}: raise ValueError('Invalid field settings.')
        if v['mode'] not in ('higher','lower','target') or v['scale'] not in ('percentile','fixed'): raise ValueError('Invalid field scoring mode.')
        limit=10 if key=='averageRating' else 9999 if key=='startYear' else 1000000000
        for part in ('low','high','target'): number(v[part],0,limit)
        number(v['tolerance'],0.01,1000000000)
        if v['low']>=v['high']: raise ValueError(f'{LABELS[key]}: low anchor must be below high anchor.')
    return copy.deepcopy(data)

def read():
    with LOCK:
        return validate(json.loads(PATH.read_text())) if PATH.exists() else validate()

def save(data):
    data=validate(data)
    with LOCK:
        name=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',dir=PATH.parent,delete=False) as f:
                name=f.name;json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(name,PATH)
        finally:
            if name and os.path.exists(name): os.unlink(name)
    return data

def utility(key,value,settings):
    if value is None or value=='': return None
    if key=='genres':
        genres=value.split(',')
        return sum(settings['genrePoints'].get(g,0) for g in genres)/len(genres)
    if key=='isAdult': return settings['adultScores'][str(value)]
    field=settings['fields'][key]
    return -abs(value-field['target']) if field['mode']=='target' else -value if field['mode']=='lower' else value

def mapping(key,counts,settings):
    utilities={value:utility(key,value,settings) for value,count in counts}
    distribution=Counter()
    for value,count in counts:
        if utilities[value] is not None: distribution[utilities[value]]+=count
    total=sum(distribution.values());less=0;percentiles={}
    for value,count in sorted(distribution.items()):
        percentiles[value]=100*(less+count/2)/total
        less+=count
    result={}
    for value,u in utilities.items():
        if u is None: score=settings['missingScore']
        elif key=='isAdult': score=u
        elif (settings['genreMode'] if key=='genres' else settings['fields'][key]['scale'])=='percentile': score=percentiles[u]
        elif key=='genres': score=(u+10)*5
        else:
            field=settings['fields'][key]
            if field['mode']=='target': score=100*(1-abs(value-field['target'])/field['tolerance'])
            else:
                score=100*(value-field['low'])/(field['high']-field['low'])
                if field['mode']=='lower': score=100-score
        result[value]=max(0,min(100,score))
    return result

def ensure_cache(settings,source=None):
    """Build once per settings/snapshot; atomically replace the derived cache."""
    source=source or ROOT/'movies.sqlite3'
    stamp=source.stat()
    signature=hashlib.sha256((json.dumps(settings,sort_keys=True)+str((str(source),stamp.st_mtime_ns,stamp.st_size))).encode()).hexdigest()
    cache=ROOT/'global_scores.sqlite3'
    with LOCK:
        if cache.exists():
            with closing(sqlite3.connect(cache)) as db:
                if db.execute('SELECT signature FROM cache_info').fetchone()[0]==signature: return cache
        fd,name=tempfile.mkstemp(suffix='.sqlite3',dir=ROOT);os.close(fd)
        try:
            with closing(sqlite3.connect(f'file:{source}?mode=ro',uri=True)) as src, closing(sqlite3.connect(name)) as dst:
                maps={key:mapping(key,src.execute(f'SELECT {key},COUNT(*) FROM movies GROUP BY {key}').fetchall(),settings) for key in LABELS}
                dst.execute('CREATE TABLE cache_info(signature TEXT)');dst.execute('INSERT INTO cache_info VALUES (?)',(signature,))
                dst.execute('CREATE TABLE scores(tconst TEXT PRIMARY KEY, globalScore REAL,'+','.join('g_'+key+' REAL' for key in LABELS)+')')
                weight=sum(settings['weights'].values())
                def records():
                    for row in src.execute('SELECT tconst,'+','.join(LABELS)+' FROM movies'):
                        scores=[maps[key][value] for key,value in zip(LABELS,row[1:])]
                        overall=round(sum(score*settings['weights'][key] for key,score in zip(LABELS,scores))/weight,1) if weight else None
                        yield (row[0],overall,*scores)
                dst.executemany('INSERT INTO scores VALUES (?,?,?,?,?,?,?,?)',records())
                dst.execute('CREATE INDEX score_order ON scores(globalScore DESC,tconst)');dst.commit()
            os.replace(name,cache)
        finally:
            if os.path.exists(name): os.unlink(name)
    return cache

def attach(db):
    # Hold the lock until the file is attached so settings and scores always agree.
    with LOCK:
        settings=read();path=ensure_cache(settings)
        db.execute('ATTACH DATABASE ? AS global_cache',(str(path),))
        return settings
