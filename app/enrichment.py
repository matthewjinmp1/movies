"""Indexed local MDBList fields; never makes network requests."""
from contextlib import closing
import json
import math
import os
import tempfile
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'mdblist_data'
CACHE = ROOT / 'mdblist.sqlite3'
LOCK = threading.RLock()
RATINGS = {'tomatoes':('rtCritic','Rotten Tomatoes critics',100),'popcorn':('rtAudience','Rotten Tomatoes audience',100),
 'metacritic':('metacritic','Metacritic critics',100),'metacriticuser':('metacriticUser','Metacritic users',10),
 'letterboxd':('letterboxd','Letterboxd',5),'tmdb':('tmdbRating','TMDB rating',100),
 'trakt':('traktRating','Trakt rating',100),'rogerebert':('ebertRating','Roger Ebert',4)}
SPECS = []
def field(key,label,kind='number',maximum=100,lower=False):
    SPECS.append(dict(key=key,label=label,kind=kind,maximum=maximum,lower=lower))
for source,(key,label,maximum) in RATINGS.items():
    field(key,label,maximum=maximum)
    field(key+'Votes',label+' votes',maximum=10000000)
for key,label,maximum,lower in [('mdbScore','MDBList score',100,False),('budget','Budget ($)',1000000000,False),('revenue','Revenue ($)',10000000000,False),('ageRating','Suggested minimum age',18,True),('violence','Violence level',5,True),('nudity','Sex / nudity level',5,True),('languageLevel','Strong language level',5,True),('drinking','Drinking / drugs level',5,True)]:
    field(key,label,maximum=maximum,lower=lower)
for key,label in [('keywords','Keywords'),('streams','Streaming services'),('watchProviders','Watch providers'),('productionCompanies','Production companies'),('language','Original language'),('country','Country'),('certification','Certification')]: field(key,label,'category')
for key,label in [('description','Plot'),('tagline','Tagline'),('released','Release date'),('releasedDigital','Digital release'),('awards','Awards'),('mdbFetched','MDBList fetched'),('poster','Poster'),('trailer','Trailer')]: field(key,label,'text')
field('mdbAvailable','MDBList data','boolean')
NUMERIC = {s['key']:s for s in SPECS if s['kind']=='number'}
CATEGORIES = {s['key']:s for s in SPECS if s['kind']=='category'}
BY_KEY = {s['key']:s for s in SPECS}

def numeric(value):
    return value if type(value) in (int,float) and math.isfinite(value) else None

def flatten(record):
    d=record['data'];r={s['key']:None for s in SPECS};r['mdbAvailable']=1
    for rating in d.get('ratings',[]):
        if rating.get('source') in RATINGS:
            key,_,_=RATINGS[rating['source']]
            r[key]=numeric(rating.get('value'));r[key+'Votes']=numeric(rating.get('votes'))
    for key,source in [('mdbScore','score'),('budget','budget'),('revenue','revenue'),('ageRating','age_rating')]:
        r[key]=numeric(d.get(source))
    for key in ('budget','revenue'):
        if r[key]==0:r[key]=None
    parental=d.get('commonsense_media') or {}
    for key,source in [('violence','parental_violence'),('nudity','parental_nudity'),('languageLevel','parental_language'),('drinking','parental_drinking')]:r[key]=numeric(parental.get(source))
    for key,source in [('keywords','keywords'),('streams','streams'),('watchProviders','watch_providers'),('productionCompanies','production_companies')]:
        r[key]=json.dumps([v['name'] for v in d.get(source,[]) if isinstance(v,dict) and v.get('name')])
    for key in ('language','country','certification'):
        value=d.get(key);r[key]=json.dumps([str(v).strip() for v in (value if isinstance(value,list) else str(value).split(',')) if v]) if value else None
    for key,source in [('description','description'),('tagline','tagline'),('released','released'),('releasedDigital','released_digital'),('awards','awards'),('poster','poster'),('trailer','trailer')]:
        value=d.get(source);r[key]=value if isinstance(value,str) else json.dumps(value) if value else None
    r['mdbFetched']=record.get('fetched_at')
    return r

def ensure():
    with LOCK:
        stamp='schema-1:'+str(DATA.stat().st_mtime_ns if DATA.exists() else 0)
        if CACHE.exists():
            with closing(sqlite3.connect(CACHE)) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='cache_info'").fetchone() and db.execute('SELECT stamp FROM cache_info').fetchone()[0]==stamp:return CACHE
        fd,name=tempfile.mkstemp(suffix='.sqlite3',dir=ROOT);os.close(fd)
        try:
            with closing(sqlite3.connect(name)) as db, db:
                db.execute('CREATE TABLE cache_info(stamp TEXT)');db.execute('INSERT INTO cache_info VALUES (?)',(stamp,))
                db.execute('CREATE TABLE enrichment(tconst TEXT PRIMARY KEY,'+','.join(s['key']+' '+('REAL' if s['kind']=='number' else 'INTEGER' if s['kind']=='boolean' else 'TEXT') for s in SPECS)+')')
                for path in sorted(DATA.glob('tt*.json')):
                    if path.name.endswith('.error.json'):continue
                    record=json.loads(path.read_text());r=flatten(record)
                    db.execute('INSERT INTO enrichment VALUES ('+','.join('?' for _ in range(len(SPECS)+1))+')',[record['imdb_id']]+[r[s['key']] for s in SPECS])
            os.replace(name,CACHE)
        finally:
            if os.path.exists(name):os.unlink(name)
        return CACHE

def attach(db):
    db.execute('ATTACH DATABASE ? AS mdb',(str(ensure()),))
    db.execute('CREATE TEMP VIEW movies AS SELECT m.*,'+','.join(('COALESCE(e.mdbAvailable,0) AS mdbAvailable' if s['key']=='mdbAvailable' else 'e.'+s['key']) for s in SPECS)+' FROM main.movies m LEFT JOIN mdb.enrichment e USING(tconst)')

def options():
    with closing(sqlite3.connect(ensure())) as db:
        return {key:[row[0] for row in db.execute(f'SELECT DISTINCT j.value FROM enrichment,json_each(enrichment.{key}) j ORDER BY j.value COLLATE NOCASE')] for key in CATEGORIES}
