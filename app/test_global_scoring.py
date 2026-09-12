import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import global_scoring as g
from server import query

class GlobalScoreTests(unittest.TestCase):
    def test_genre_average_and_population_ties(self):
        s=g.validate();s['genrePoints']={'Thriller':3,'Horror':-1}
        self.assertEqual(g.utility('genres','Thriller,Horror',s),1)
        self.assertEqual(g.utility('genres','Thriller,Drama',s),1.5)
        scores=g.mapping('genres',[('Horror',2),('Thriller,Horror',4),('Thriller',2),(None,3)],s)
        self.assertEqual(scores,{'Horror':12.5,'Thriller,Horror':50,'Thriller':87.5,None:0})
        self.assertEqual(g.mapping('genres',[('Drama',8),('Comedy',2)],s),{'Drama':50,'Comedy':50})
        s['genreMode']='fixed'
        self.assertEqual(g.mapping('genres',[('Thriller,Horror',1)],s)['Thriller,Horror'],55)

    def test_numeric_preferences_and_missing(self):
        s=g.validate();f=s['fields']['runtimeMinutes'];f.update(mode='target',scale='fixed',target=120,tolerance=30)
        scores=g.mapping('runtimeMinutes',[(60,1),(90,1),(120,1),(135,1),(150,1),(None,1)],s)
        self.assertEqual(scores,{60:0,90:0,120:100,135:50,150:0,None:0})
        f.update(mode='lower',scale='percentile')
        scores=g.mapping('runtimeMinutes',[(90,1),(120,1),(150,1)],s)
        self.assertGreater(scores[90],scores[120]);self.assertGreater(scores[120],scores[150])
        s['missingScore']=50
        self.assertEqual(g.mapping('averageRating',[(None,10)],s)[None],50)

    def test_settings_persist_and_validate(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(g,'PATH',Path(directory)/'settings.json'):
            s=g.validate();s['genrePoints']={'Thriller':3,'Horror':-1};g.save(s)
            self.assertEqual(g.read(),s)
            s['weights']['genres']=-1
            with self.assertRaises(ValueError):g.save(s)
            self.assertEqual(g.read()['weights']['genres'],1)

    def test_global_ranking_independent_of_filters(self):
        result=query({'sort':['globalScore'],'direction':['desc']})
        values=[row['globalScore'] for row in result['rows']]
        self.assertEqual(values,sorted(values,reverse=True))
        row=result['rows'][0]
        single=query({'q':[row['tconst']]})['rows'][0]
        self.assertEqual(row['globalScore'],single['globalScore'])
        self.assertEqual(row['globalRank'],1)
        self.assertEqual(row['globalRank'],single['globalRank'])
        ranked=query({'sort':['globalRank'],'direction':['asc']})
        self.assertEqual([r['tconst'] for r in result['rows']],[r['tconst'] for r in ranked['rows']])
        import sqlite3
        with sqlite3.connect(g.ROOT/'global_scores.sqlite3') as db:
            for movie in ranked['rows']:
                expected=1+db.execute('SELECT COUNT(*) FROM scores WHERE globalScore > ?',(movie['globalScore'],)).fetchone()[0]
                self.assertEqual(movie['globalRank'],expected)
        self.assertEqual(row['globalBreakdown'],single['globalBreakdown'])
        parts=row['globalBreakdown'];weight=sum(p['weight'] for p in parts)
        self.assertAlmostEqual(row['globalScore'],sum(p['score']*p['weight'] for p in parts)/weight,delta=0.1)

    def test_all_weights_zero(self):
        s=g.validate();s['weights']={key:0 for key in g.LABELS}
        with tempfile.TemporaryDirectory() as directory,patch.object(g,'ROOT',Path(directory)):
            path=g.ensure_cache(s,Path(__file__).parent/'movies.sqlite3')
            import sqlite3
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM scores WHERE globalScore IS NOT NULL').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ranks WHERE globalRank IS NOT NULL').fetchone()[0],0)
