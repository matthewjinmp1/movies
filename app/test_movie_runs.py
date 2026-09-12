import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import movie_runs as runs


class MovieRunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch = patch.object(runs, 'PATH', Path(self.directory.name)/'runs.sqlite3')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def selection(self):
        saved = runs.save_list({'name':'Test movies','ids':['tt1375666','tt0111161','tt1375666']})
        return {'name':'Suspense','prompt':'Rate MOVIE','list_id':saved['id'],
                'count':2,'workers':2,'max_tokens':1000}

    def test_movie_placeholder_includes_year(self):
        movie = {'primaryTitle':'Inception', 'startYear':2010, 'tconst':'tt1375666'}
        prompt = runs.rendered_prompt('Rate {{MOVIE}}; year {{YEAR}}; id {{IMDB_ID}}.', movie)
        self.assertTrue(prompt.startswith('Rate Inception (2010); year 2010; id tt1375666.'))
        movie['startYear'] = None
        self.assertTrue(runs.rendered_prompt('Rate {{MOVIE}}.', movie).startswith('Rate Inception.'))

    def test_plain_movie_keyword(self):
        movie = {'primaryTitle':'The MOVIE {{YEAR}}', 'startYear':2010, 'tconst':'tt123'}
        prompt = runs.rendered_prompt('Rate MOVIE. MOVIE/MOVIES movie {{MOVIE}}', movie)
        self.assertEqual(prompt.split('\n\n')[0],
                         'Rate The MOVIE {{YEAR}} (2010). The MOVIE {{YEAR}} (2010)/MOVIES movie The MOVIE {{YEAR}} (2010)')
        movie['startYear'] = None
        self.assertTrue(runs.rendered_prompt('Rate MOVIE.', movie).startswith('Rate The MOVIE {{YEAR}}.'))

    def test_snapshot_and_list_edit(self):
        p = self.selection()
        run_id = runs.create(p, launch=False)
        runs.save_list({'id':p['list_id'],'name':'Edited','ids':['tt0111161']})
        self.assertEqual(len(runs.detail(run_id)['items']),2)
        self.assertEqual(runs.detail(run_id)['list_name'],'Test movies')
        self.assertEqual(runs.lists()[0]['count'],1)
        self.assertEqual(runs.history()[0]['total'],2)
        with self.assertRaises(ValueError):
            runs.save_list({'name':'Bad','ids':['tt9999999999999999']})
        self.assertEqual(runs.lists()[0]['count'],1)

    def test_worker_saves_scores_usage_and_errors(self):
        run_id = runs.create(self.selection(), launch=False)
        with runs.database() as db:
            db.execute("UPDATE runs SET status='running',pid=? WHERE id=?", (runs.os.getpid(),run_id))
        def response(*args, **kwargs):
            return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"score":87,"explanation":"Strong fit"}'},'finish_reason':'stop'}],
                       'usage':{'prompt_tokens':100,'completion_tokens':25,'cost':0.001},'provider':'Test'}).encode())
        with patch.object(runs.urllib.request, 'urlopen', side_effect=response), patch.object(runs.chat,'load_local_env'):
            runs.worker(run_id)
        result = runs.detail(run_id)
        self.assertEqual(result['status'],'completed')
        self.assertEqual([i['score'] for i in result['items']],[87,87])
        self.assertEqual(len(result['attempts']),2)
        self.assertEqual(sum(a['cost'] for a in result['attempts']),0.002)
        runs.action(run_id,'star')
        self.assertEqual(runs.detail(run_id)['starred'],1)
        with self.assertRaises(ValueError): runs.action(run_id,'resume')

    def test_stop_and_interruption(self):
        run_id = runs.create(self.selection(),launch=False)
        with runs.database() as db:
            db.execute("UPDATE runs SET status='running',pid=? WHERE id=?", (runs.os.getpid(),run_id))
        runs.action(run_id,'stop')
        with patch.object(runs.urllib.request,'urlopen') as request:
            runs.worker(run_id)
            request.assert_not_called()
        self.assertEqual(runs.detail(run_id)['status'],'stopped')
        with runs.database() as db:
            db.execute("UPDATE runs SET status='running',pid=99999999 WHERE id=?", (run_id,))
            db.execute("UPDATE items SET status='scoring' WHERE run_id=?", (run_id,))
        result=runs.detail(run_id)
        self.assertEqual(result['status'],'interrupted')
        self.assertTrue(all(i['status']=='queued' for i in result['items']))

    def test_failed_response_retry_preserves_attempts(self):
        run_id=runs.create(self.selection(),launch=False)
        with runs.database() as db:
            db.execute("UPDATE runs SET status='running',pid=? WHERE id=?", (runs.os.getpid(),run_id))
        with patch.object(runs.urllib.request,'urlopen',side_effect=TimeoutError('Test timeout')), patch.object(runs.time,'sleep'), patch.object(runs.chat,'load_local_env'):
            runs.worker(run_id)
        result=runs.detail(run_id)
        self.assertEqual(len(result['attempts']),6)
        self.assertTrue(all(i['status']=='failed' for i in result['items']))
        with patch.object(runs,'start') as start:
            runs.action(run_id,'retry')
            start.assert_called_once()
        self.assertTrue(all(i['status']=='queued' for i in runs.detail(run_id)['items']))
        self.assertEqual(len(runs.detail(run_id)['attempts']),6)

    def test_score_and_preview_validation(self):
        self.assertEqual(runs.parse_score('```json\n{"score":70}\n```'),70)
        for value in ['{"score":null}','{"score":true}','{"score":101}','{"score":NaN}','Some text 95 then more text','score: -1','score: 101','score: 1e999']:
            with self.assertRaises(ValueError): runs.parse_score(value)
        for text, expected in [('Some text 95',95), ('Misery (1990), rating 7.8.\n\nscore: 88',88), ('Score: 87.5. ',87.5), ('88',88), ('score: 0',0), ('score: 100',100)]:
            self.assertEqual(runs.parse_score(text),expected)
        p=self.selection()
        for field,value in [('count',3),('workers',0),('max_tokens',0),('prompt','')]:
            with self.assertRaises(ValueError): runs.preview(dict(p,**{field:value}))


if __name__=='__main__':
    unittest.main()
