"""Local movie browser. Python standard library only; no external services."""
import argparse
import json
import math
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from functools import lru_cache
from contextlib import closing
from scoring import score_components
import preferences
import score_settings
import starred
import global_scoring

ROOT = Path(__file__).resolve().parent
COLUMNS = [
    ('globalScore','Global score','number'),
    ('primaryTitle','Title','text'), ('filterScore','Filter score','number'), ('originalTitle','Original title','text'),
    ('startYear','Year','number'), ('averageRating','IMDb rating','number'),
    ('numVotes','Votes','number'), ('runtimeMinutes','Runtime (min)','number'),
    ('genres','Genres','genre'), ('isAdult','Adult','boolean'),
    ('tconst','IMDb ID','text'), ('titleType','Title type','text'), ('endYear','End year','number'),
]
FIELDS = {key:kind for key,_,kind in COLUMNS}

def connect(saved_ids=()):
    db = sqlite3.connect(f'file:{ROOT / "movies.sqlite3"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.create_function('CASEFOLD', 1, lambda s: s.casefold() if s is not None else None, deterministic=True)
    db.create_function('LOG10PLUS', 1, lambda n: math.log10(max(0,n)+1), deterministic=True)
    db.create_function('SCOREPOWER', 2, lambda value,power: value**power, deterministic=True)
    db.execute('CREATE TEMP TABLE saved_movies (tconst TEXT PRIMARY KEY)')
    db.executemany('INSERT INTO saved_movies VALUES (?)', ((v,) for v in saved_ids))
    return db

def conditions(search, filters):
    clauses, args = [], []
    if search:
        clauses.append("(instr(CASEFOLD(primaryTitle), ?) > 0 OR instr(CASEFOLD(originalTitle), ?) > 0 OR instr(tconst, ?) > 0)")
        args.extend([search.casefold()]*3)
    if not isinstance(filters,list) or len(filters)>30:
        raise ValueError('Use at most 30 filters.')
    for f in filters:
        if not isinstance(f,dict) or f.get('field') not in FIELDS or f.get('field') in ('filterScore','globalScore'):
            raise ValueError('Unknown filter field.')
        key, op, value = f['field'], f.get('op'), f.get('value')
        kind = FIELDS[key]
        if op in ['missing','present']:
            clauses.append(f'{key} IS '+('NOT NULL' if op=='present' else 'NULL'))
        elif kind == 'number' and op in ['eq','gte','lte']:
            try: number = float(value)
            except (TypeError,ValueError): raise ValueError('Enter a valid number.')
            if not math.isfinite(number): raise ValueError('Enter a finite number.')
            clauses.append(f'{key} '+{'eq':'=','gte':'>=','lte':'<='}[op]+' ?')
            args.append(number)
        elif kind == 'boolean' and op=='eq' and str(value) in ['0','1']:
            clauses.append(f'{key} = ?'); args.append(int(value))
        elif kind == 'genre' and op in ['any_of','all_of']:
            if not isinstance(value,list) or not value or len(value)>30 or any(not isinstance(v,str) or not v or ',' in v for v in value):
                raise ValueError('Select one or more valid genres.')
            joiner = ' OR ' if op == 'any_of' else ' AND '
            clauses.append('(' + joiner.join([f"instr(',' || {key} || ',', ?) > 0"] * len(value)) + ')')
            args.extend(',' + v + ',' for v in value)
        elif kind == 'genre' and op in ['has','not_has'] and isinstance(value,str) and value:
            clauses.append(f"instr(',' || {key} || ',', ?) "+('= 0' if op=='not_has' else '> 0'))
            args.append(','+value+',')
        elif kind == 'text' and op in ['contains','eq','not_contains'] and isinstance(value,str):
            if op=='eq': clauses.append(f'CASEFOLD({key}) = ?')
            else: clauses.append(f'instr(CASEFOLD({key}), ?) '+('= 0' if op=='not_contains' else '> 0'))
            args.append(value.casefold())
        else:
            raise ValueError('Invalid filter operator or value.')
    return (' WHERE '+' AND '.join(clauses) if clauses else ''), args

@lru_cache(maxsize=128)
def count_matches(search, encoded, saved_ids=None):
    where,args = conditions(search,json.loads(encoded))
    if saved_ids is not None:
        where += (' AND ' if where else ' WHERE ') + 'tconst IN (SELECT tconst FROM saved_movies)'
    with closing(connect(saved_ids or ())) as db:
        return db.execute('SELECT count(*) FROM movies'+where,args).fetchone()[0]

def query(params):
    search = params.get('q',[''])[0][:500]
    filters = json.loads(params.get('filters',['[]'])[0])
    where,args = conditions(search,filters)
    saved_ids = starred.read()
    saved_view = params.get('view',['all'])[0] == 'starred'
    if saved_view:
        where += (' AND ' if where else ' WHERE ') + 'tconst IN (SELECT tconst FROM saved_movies)'
    sort = params.get('sort',['numVotes'])[0]
    direction = params.get('direction',['desc'])[0]
    if sort not in FIELDS or direction not in ['asc','desc']: raise ValueError('Invalid sort.')
    size = int(params.get('size',['50'])[0])
    if size not in [25,50,100,250]: raise ValueError('Invalid page size.')
    total = count_matches(search,json.dumps(filters,sort_keys=True),tuple(sorted(saved_ids)) if saved_view else None)
    pages = max(1,math.ceil(total/size))
    page = max(1,min(int(params.get('page',['1'])[0]),pages))
    collation = ' COLLATE NOCASE' if FIELDS[sort] in ['text','genre'] else ''
    settings=score_settings.validate(json.loads(params.get('scoring',['null'])[0]))
    components = score_components(filters, search, settings)
    extra = ''.join(f', ({c["sql"]}) AS score_{i}' for i,c in enumerate(components))
    score_args = [v for c in components for v in c['args']]
    weight=sum(c['weight'] for c in components)
    score = 'ROUND(100.0 * (' + ' + '.join(f'score_{i} * {c["weight"]}' for i,c in enumerate(components)) + f') / {weight}, 1)' if weight else 'NULL'
    with closing(connect(saved_ids if saved_view else ())) as db:
        global_settings=global_scoring.attach(db)
        rows = db.execute(f'SELECT *, {score} AS filterScore FROM (SELECT *{extra} FROM movies JOIN global_cache.scores USING(tconst){where}) ORDER BY {sort}{collation} {direction} NULLS LAST, tconst ASC LIMIT ? OFFSET ?',score_args+args+[size,(page-1)*size]).fetchall()
    result=[]
    for record in rows:
        row=dict(record)
        row['starred'] = row['tconst'] in saved_ids
        row['globalBreakdown']=[dict(label=label,weight=global_settings['weights'][key],score=round(row.pop('g_'+key),1),raw=global_scoring.utility(key,row[key],global_settings) if key=='genres' else row[key]) for key,label in global_scoring.LABELS.items()]
        row['scoreBreakdown']=[dict(label=c['label'],weight=c['weight'],score=round(100*row.pop(f'score_{i}'),1)) for i,c in enumerate(components)]
        result.append(row)
    return dict(rows=result,total=total,page=page,pages=pages,size=size,starredCount=len(saved_ids),scoreRules=[dict(label=c['label'],rule=c['rule'],weight=c['weight']) for c in components])

class Handler(BaseHTTPRequestHandler):
    def do_PUT(self):
        path = urlsplit(self.path).path
        if path not in ('/api/filters','/api/starred','/api/global-scoring'):
            return self.send_json({'error':'Not found'},404)
        origin=self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host',''):
            return self.send_json({'error':'Origin not allowed'},403)
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.send_json({'error':'JSON required'},415)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384: raise ValueError('Invalid settings size.')
            payload = json.loads(self.rfile.read(size))
            if path == '/api/global-scoring':
                return self.send_json({'settings':global_scoring.save(payload),'saved':True})
            if path == '/api/starred':
                if not isinstance(payload,dict): raise ValueError('Invalid selection.')
                movie_id = payload.get('tconst')
                with closing(connect()) as db:
                    if not isinstance(movie_id,str) or not db.execute('SELECT 1 FROM movies WHERE tconst=?',(movie_id,)).fetchone():
                        raise ValueError('Movie not found.')
                count = starred.update(movie_id,payload.get('starred'))
                return self.send_json({'saved':True,'starredCount':count})
            preferences.save(payload)
            return self.send_json({'saved':True})
        except (ValueError,TypeError,KeyError) as error:
            return self.send_json({'error':str(error)},400)
        except OSError:
            return self.send_json({'error':'Could not save your changes.'},500)

    def do_GET(self):
        parsed = urlsplit(self.path)
        try:
            if parsed.path == '/api/filters':
                return self.send_json(preferences.read())
            if parsed.path == '/api/global-scoring':
                return self.send_json({'settings':global_scoring.read(),'defaults':global_scoring.validate()})
            if parsed.path == '/api/movies':
                return self.send_json(query(parse_qs(parsed.query)))
            if parsed.path == '/api/meta':
                with closing(connect()) as db: meta = json.loads(db.execute('SELECT value FROM metadata').fetchone()[0])
                meta['columns'] = [dict(key=k,label=l,kind=t) for k,l,t in COLUMNS]
                meta['scoringDefaults']=score_settings.validate()
                return self.send_json(meta)
            files = {'/':('index.html','text/html'), '/app.js':('app.js','text/javascript'), '/global.js':('global.js','text/javascript'), '/styles.css':('styles.css','text/css')}
            if parsed.path not in files: return self.send_json({'error':'Not found'},404)
            name,mime = files[parsed.path]
            self.send_bytes((ROOT/'dist'/name).read_bytes(),mime+'; charset=utf-8')
        except (ValueError,TypeError,KeyError) as e:
            self.send_json({'error':str(e)},400)
        except Exception:
            import traceback; traceback.print_exc()
            self.send_json({'error':'Could not load movies. Please try again.'},500)

    def send_json(self,data,status=200):
        self.send_bytes(json.dumps(data,ensure_ascii=False).encode(),'application/json; charset=utf-8',status)

    def send_bytes(self,data,mime,status=200):
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'self'; base-uri 'none'")
        self.end_headers(); self.wfile.write(data)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=3002); options=parser.parse_args()
    if not (ROOT/'movies.sqlite3').exists():
        from import_data import build
        build()
    server=ThreadingHTTPServer(('127.0.0.1',options.port),Handler)
    print(f'Movie browser: http://127.0.0.1:{options.port}',flush=True)
    server.serve_forever()
