"""Build a local, joined movie index from the downloaded IMDb snapshots."""
import csv
import gzip
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'app' / 'movies.sqlite3'

def build():
    temporary = DB.with_suffix('.building')
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('CREATE TABLE basics (tconst TEXT PRIMARY KEY, titleType TEXT, primaryTitle TEXT COLLATE NOCASE, originalTitle TEXT COLLATE NOCASE, isAdult INTEGER, startYear INTEGER, endYear INTEGER, runtimeMinutes INTEGER, genres TEXT)')
    with (ROOT / 'movies.csv').open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        def records():
            for r in reader:
                yield tuple(None if v == '\\N' else int(v) if k in {'isAdult','startYear','endYear','runtimeMinutes'} else v for k,v in r.items())
        db.executemany('INSERT INTO basics VALUES (?,?,?,?,?,?,?,?,?)', records())
    print('Movies imported; joining ratings…', flush=True)
    db.execute('CREATE TABLE ratings (tconst TEXT PRIMARY KEY, averageRating REAL, numVotes INTEGER)')
    with gzip.open(ROOT / 'title.ratings.tsv.gz', 'rt', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        db.executemany('INSERT INTO ratings VALUES (?,?,?)', ((r['tconst'],float(r['averageRating']),int(r['numVotes'])) for r in reader))
    db.execute('CREATE TABLE movies AS SELECT basics.*, ratings.averageRating, ratings.numVotes FROM basics LEFT JOIN ratings USING(tconst)')
    db.execute('CREATE UNIQUE INDEX idx_movies_id ON movies(tconst)')
    for column in ['primaryTitle','startYear','averageRating','numVotes','runtimeMinutes']:
        db.execute(f'CREATE INDEX idx_movies_{column} ON movies({column}'+ (' COLLATE NOCASE)' if column=='primaryTitle' else ')'))
    db.execute('CREATE TABLE metadata (value TEXT)')
    stats = dict(zip(['total','rated'], db.execute('SELECT count(*),count(averageRating) FROM movies').fetchone()))
    genres = sorted({g for (value,) in db.execute('SELECT DISTINCT genres FROM movies WHERE genres IS NOT NULL') for g in value.split(',')})
    stats['genres'] = genres
    stats['snapshot'] = datetime.fromtimestamp((ROOT/'title.ratings.tsv.gz').stat().st_mtime, timezone.utc).date().isoformat()
    db.execute('INSERT INTO metadata VALUES (?)', (json.dumps(stats),))
    db.execute('DROP TABLE basics')
    db.execute('DROP TABLE ratings')
    db.commit()
    db.execute('VACUUM')
    db.execute('PRAGMA optimize')
    db.close()
    temporary.replace(DB)
    print(json.dumps(stats), flush=True)

if __name__ == '__main__':
    build()
