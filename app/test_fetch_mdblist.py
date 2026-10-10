import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_mdblist as fetch


def reply(payload):
    response = io.BytesIO(json.dumps(payload).encode())
    response.headers = {}
    return response


def run(root, responses, argv=()):
    with patch.object(fetch,'DIRECTORY',root), patch.object(fetch.chat,'load_local_env'), patch.dict(fetch.os.environ,{'MDBList_KEY':'test'}), \
         patch.object(sys,'argv',['fetch_mdblist.py',*argv]), patch.object(fetch.time,'sleep'), patch.object(fetch.seen,'read',return_value=set()), \
         patch.object(fetch,'refresh_caches') as refresh, patch.object(fetch.urllib.request,'urlopen',side_effect=responses) as request:
        fetch.main()
        return request.call_count, refresh.call_count


class DownloadTests(unittest.TestCase):
    def test_full_response_saved_and_resume_skips_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch.save(root/'selection.json', {'movies':[{'tconst':'tt123','primaryTitle':'Test'}]})
            response = reply({'ids':{'imdb':'tt123'},'ratings':[{'source':'tomatoes','value':88}], 'extra':{'example':True}})
            self.assertEqual(run(root, [response]), (1,1))
            self.assertEqual(run(root, []), (0,0))
            saved = json.loads((root/'tt123.json').read_text())
            self.assertTrue(saved['data']['extra']['example'])
            self.assertFalse(list((root/'incoming').iterdir()))
            self.assertEqual(json.loads((root/'state'/'summary.json').read_text())['remaining'],0)
            self.assertFalse((root/'selection.json').exists())

    def test_movie_without_ratings_is_skipped_without_stopping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch.save(root/'selection.json', {'movies':[{'tconst':'tt1','primaryTitle':'Empty'},{'tconst':'tt2','primaryTitle':'Full'}]})
            pool = fetch.concurrent.futures.ThreadPoolExecutor
            with patch.object(fetch.concurrent.futures,'ThreadPoolExecutor',lambda max_workers: pool(1)):
                self.assertEqual(run(root, [reply({'ids':{'imdb':'tt1'},'ratings':[]}), reply({'ids':{'imdb':'tt2'},'ratings':[{'source':'imdb','value':7}]})]), (2,1))
            self.assertTrue((root/'tt1.error.json').exists())
            self.assertTrue((root/'tt2.json').exists())
            self.assertEqual(run(root, []), (0,0))

    def test_daily_run_stops_when_quota_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch.save(root/'selection.json', {'movies':[{'tconst':'tt123','primaryTitle':'Test'}]})
            self.assertEqual(run(root, [reply({'rate_limit_remaining':0})], ['--daily']), (1,0))
            self.assertFalse((root/'tt123.json').exists())

    def test_vote_bands_fill_in_order(self):
        calls = []
        def query(params):
            filters = json.loads(params['filters'][0])
            calls.append([f['value'] for f in filters if f['field']=='numVotes'])
            band = calls[-1][0]
            return {'rows':[{'tconst':f'tt{band}{i}','primaryTitle':'Movie','startYear':2000,'numVotes':int(band),'globalScore':50} for i in range(2)],'pages':1}
        with patch.object(fetch.server,'query',side_effect=query):
            movies = fetch.top_movies(3, set(), 25000)
        self.assertEqual(calls, [['100000'],['50000','99999']])
        self.assertEqual([m['tconst'] for m in movies], ['tt1000000','tt1000001','tt500000'])
