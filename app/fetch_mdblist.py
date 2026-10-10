"""Fetch full MDBList records for seen movies and the biggest, best-scoring movies first."""
import argparse
import concurrent.futures
import fcntl
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
import global_scoring
import seen
import server

DIRECTORY = Path(__file__).resolve().parent / 'mdblist_data'
# Bigger movies come first: each IMDb vote band is filled in global-score order before the next smaller band.
VOTE_TIERS = (100000, 50000, 25000, 10000, 5000, 1000)


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def publish(incoming):
    # Records are staged so the running app rebuilds its caches once per run, not after every download.
    if incoming.exists():
        for path in sorted(incoming.glob('tt*.json')):
            path.replace(DIRECTORY / path.name)


def refresh_caches():
    # Rebuild the derived caches here so the app does not pause on its next request.
    global_scoring.ensure_cache(global_scoring.read())


def request_json(url):
    request = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'FrameMovieLibrary/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response), {k:v for k,v in response.headers.items() if any(x in k.lower() for x in ('limit','remaining','quota'))}


def remaining_quota(key):
    return int(request_json('https://api.mdblist.com/user?'+urllib.parse.urlencode({'apikey':key}))[0]['rate_limit_remaining'])


def candidates(params, limit, known, reason):
    """Rows from a library query that are not yet selected, in query order."""
    found = []
    page = 1
    while limit is None or len(found) < limit:
        result = server.query(dict(params, page=[str(page)]))
        for row in result['rows']:
            if row['tconst'] not in known:
                known.add(row['tconst'])
                found.append({key:row[key] for key in ('tconst','primaryTitle','startYear','numVotes','globalScore')} | {'reason':reason})
        if page >= result['pages']:
            break
        page += 1
    return found if limit is None else found[:limit]


def top_movies(limit, known, min_votes):
    found = []
    ceiling = None
    for tier in [t for t in VOTE_TIERS if t > min_votes] + [min_votes]:
        filters = [{'field':'numVotes','op':'gte','value':str(tier)}, {'field':'notSeen','op':'eq','value':True}]
        if ceiling:
            filters.append({'field':'numVotes','op':'lte','value':str(ceiling-1)})
        found += candidates({'view':['all'], 'sort':['globalScore'], 'direction':['desc'], 'size':['250'], 'filters':[json.dumps(filters)]},
                            limit-len(found), known, f'top global score, {tier:,}+ votes')
        if len(found) >= limit:
            break
        ceiling = tier
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-requests', type=int, default=1000)
    parser.add_argument('--add', type=int, default=0, help='Add this many unseen movies not yet selected, biggest vote band first.')
    parser.add_argument('--min-votes', type=int, default=VOTE_TIERS[-1], help='Smallest IMDb vote count for movies added with --add.')
    parser.add_argument('--daily', action='store_true', help="Use the rest of today's MDBList quota, adding movies as needed.")
    args = parser.parse_args()
    chat.load_local_env()
    key = os.environ.get('MDBList_KEY')
    if not key:
        raise SystemExit('MDBList_KEY is missing from the local environment.')
    # Bookkeeping lives in a subfolder: the app rebuilds its caches whenever the records folder itself changes.
    state = DIRECTORY / 'state'
    state.mkdir(parents=True, exist_ok=True)
    for name in ('selection.json', 'summary.json'):
        if (DIRECTORY / name).exists():
            (DIRECTORY / name).replace(state / name)
    with open(state / '.fetch.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another MDBList download is already running.')
        download(args, key)


def download(args, key):
    print(f'{datetime.datetime.now().isoformat(timespec="seconds")}: starting MDBList download.', flush=True)
    if args.daily:
        args.max_requests = remaining_quota(key)
        if args.max_requests <= 0:
            print('No MDBList requests remain today.', flush=True)
            return
    incoming = DIRECTORY / 'incoming'
    publish(incoming)
    manifest_path = DIRECTORY / 'state' / 'selection.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {'created':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'movies':[]}
    done = lambda tconst: any((folder/(tconst+suffix)).exists() for folder in (DIRECTORY, incoming) for suffix in ('.json', '.error.json'))
    known = {m['tconst'] for m in manifest['movies']}
    # Seen movies are always included, ahead of any new top-scoring movies.
    added = candidates({'view':['seen'], 'sort':['globalScore'], 'direction':['desc'], 'size':['250'], 'filters':['[]']}, None, known, 'seen') if seen.read() - known else []
    if args.daily:
        args.add = args.max_requests - len(added) - sum(not done(m['tconst']) for m in manifest['movies'])
    if args.add > 0:
        added += top_movies(args.add, known, args.min_votes)
    if added:
        manifest['movies'].extend(added)
        manifest.setdefault('extensions', []).append({
            'created':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'min_votes':args.min_votes,
            'seen':sum(m['reason']=='seen' for m in added), 'top_global_score':sum(m['reason']!='seen' for m in added)})
        save(manifest_path, manifest)
        print(f'Added {len(added)} movies to the selection.', flush=True)
    movies = manifest['movies']
    pending_movies = [(i,m) for i,m in enumerate(movies,1) if not done(m['tconst'])][:args.max_requests]
    incoming.mkdir(exist_ok=True)
    stop = threading.Event()
    throttle = threading.Lock()
    fetched = []
    def fetch_one(entry):
        position, movie = entry
        if stop.is_set():
            return
        with throttle:
            if stop.is_set():
                return
            time.sleep(0.8)
        try:
            payload, quota = request_json('https://api.mdblist.com/imdb/movie/'+movie['tconst']+'?'+urllib.parse.urlencode({
                'apikey':key, 'append_to_response':'review,keyword,extra,recommendations'}))
            if not isinstance(payload, dict) or payload.get('error'):
                save(DIRECTORY / 'state' / 'last_error.json', {'imdb_id':movie['tconst'], 'response':payload})
                print(f'Stopped: response for {movie["tconst"]} needs inspection.', flush=True)
                stop.set()
                return
            if not payload.get('ratings'):
                # Recorded so later runs skip it instead of stopping on the same movie.
                save(incoming / (movie['tconst']+'.error.json'), {'response':payload})
                print(f'Skipped {movie["tconst"]} ({movie["primaryTitle"]}): no ratings returned.', flush=True)
                return
            returned = payload.get('imdbid') or payload.get('imdb_id') or (payload.get('ids') or {}).get('imdb')
            if returned and returned != movie['tconst']:
                raise ValueError('Returned IMDb ID does not match requested movie.')
            save(incoming / (movie['tconst']+'.json'), {'imdb_id':movie['tconst'], 'selection_rank':position,
                        'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'data':payload})
            fetched.append(movie['tconst'])
            if len(fetched) == 1 or len(fetched) % 25 == 0:
                print(f'Saved {position}/{len(movies)}: {movie["primaryTitle"]}; quota headers: {quota}', flush=True)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                save(incoming / (movie['tconst']+'.error.json'), {'status':404})
                print(f'Skipped {movie["tconst"]} ({movie["primaryTitle"]}): not found on MDBList.', flush=True)
                return
            print(f'Stopped at {position}: HTTP {error.code}; retry-after={error.headers.get("Retry-After")}; remaining={error.headers.get("x-ratelimit-remaining")}; saved records can be resumed.', flush=True)
            stop.set()
            return
        except Exception as error:
            # Never print exception URLs, which may contain the API key.
            print(f'Stopped at {position}: {type(error).__name__}; saved records can be resumed.', flush=True)
            stop.set()
            return
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(fetch_one, pending_movies))
    finally:
        publish(incoming)
    saved = sum((DIRECTORY/(m['tconst']+'.json')).exists() for m in movies)
    skipped = sum((DIRECTORY/(m['tconst']+'.error.json')).exists() for m in movies)
    save(DIRECTORY/'state'/'summary.json', {'selected':len(movies), 'saved':saved, 'skipped':skipped,
                                  'remaining':len(movies)-saved-skipped})
    print(f'Fetched {len(fetched)} this run. Saved {saved}/{len(movies)} records; {skipped} skipped.', flush=True)
    if fetched:
        refresh_caches()
        print('Library caches refreshed.', flush=True)


if __name__ == '__main__':
    main()
