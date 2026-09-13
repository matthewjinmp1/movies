"""Fetch full MDBList records for a frozen, filtered global-score selection."""
import argparse
import concurrent.futures
import threading
import time
import datetime
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

import chat
import server

DIRECTORY = Path(__file__).resolve().parent / 'mdblist_data'


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-requests', type=int, default=1000)
    args = parser.parse_args()
    chat.load_local_env()
    key = os.environ.get('MDBList_KEY')
    if not key:
        raise SystemExit('MDBList_KEY is missing from the local environment.')
    DIRECTORY.mkdir(exist_ok=True)
    manifest_path = DIRECTORY / 'selection.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        params = {'view':['all'], 'sort':['globalScore'], 'direction':['desc'], 'size':['250'],
                  'filters':[json.dumps([{'field':'numVotes','op':'gte','value':'100000'},
                                         {'field':'notSeen','op':'eq','value':True}])]}
        movies = []
        for page in range(1, 5):
            result = server.query(dict(params, page=[str(page)]))
            movies.extend(result['rows'])
            if page >= result['pages']:
                break
        manifest = {'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'query':params, 'matching_total':result['total'], 'movies':movies[:1000]}
        save(manifest_path, manifest)
    movies = manifest['movies']
    stop = threading.Event()
    throttle = threading.Lock()
    pending_movies = [(i,m) for i,m in enumerate(movies,1)
                      if not (DIRECTORY/(m['tconst']+'.json')).exists()][:args.max_requests]
    def fetch_one(entry):
        position, movie = entry
        if stop.is_set():
            return
        with throttle:
            if stop.is_set():
                return
            time.sleep(0.8)
        path = DIRECTORY / (movie['tconst']+'.json')
        url = 'https://api.mdblist.com/imdb/movie/'+movie['tconst']+'?'+urllib.parse.urlencode({
            'apikey':key, 'append_to_response':'review,keyword,extra,recommendations'})
        request = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'FrameMovieLibrary/1.0'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
                quota = {k:v for k,v in response.headers.items() if any(x in k.lower() for x in ('limit','remaining','quota'))}
            if not isinstance(payload, dict) or payload.get('error') or not payload.get('ratings'):
                save(DIRECTORY / (movie['tconst']+'.error.json'), {'response':payload})
                print(f'Stopped: response for {movie["tconst"]} needs inspection.', flush=True)
                stop.set()
                return
            returned = payload.get('imdbid') or payload.get('imdb_id') or (payload.get('ids') or {}).get('imdb')
            if returned and returned != movie['tconst']:
                raise ValueError('Returned IMDb ID does not match requested movie.')
            save(path, {'imdb_id':movie['tconst'], 'selection_rank':position,
                        'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'data':payload})
            if position == 1 or position % 25 == 0:
                print(f'Saved {position}/{len(movies)}: {movie["primaryTitle"]}; quota headers: {quota}', flush=True)
        except urllib.error.HTTPError as error:
            print(f'Stopped at {position}: HTTP {error.code}; retry-after={error.headers.get("Retry-After")}; remaining={error.headers.get("x-ratelimit-remaining")}; saved records can be resumed.', flush=True)
            stop.set()
            return
        except Exception as error:
            # Never print exception URLs, which may contain the API key.
            print(f'Stopped at {position}: {type(error).__name__}; saved records can be resumed.', flush=True)
            stop.set()
            return
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch_one, pending_movies))
    saved = sum((DIRECTORY/(m['tconst']+'.json')).exists() for m in movies)
    save(DIRECTORY/'summary.json', {'selected':len(movies), 'saved':saved,
                                  'remaining':len(movies)-saved})
    print(f'Saved {saved}/{len(movies)} records.', flush=True)


if __name__ == '__main__':
    main()
