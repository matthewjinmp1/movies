"""Integration checks against the imported personal IMDb snapshot."""
import json
import unittest
from server import query, COLUMNS, connect
from scoring import score_components
import sqlite3
import math

def get(**kwargs):
    return query({k:[json.dumps(v) if k in ('filters','scoring') else str(v)] for k,v in kwargs.items()})

class MovieBrowserTests(unittest.TestCase):
    def test_favor_newer_years(self):
        def score(year,filters):
            component=score_components(filters,settings={'yearMode':'newer'})[0]
            with sqlite3.connect(':memory:') as db:
                return db.execute('SELECT '+component['sql']+' FROM (SELECT ? AS startYear)',component['args']+[year]).fetchone()[0]
        low=dict(field='startYear',op='gte',value=2000)
        high=dict(field='startYear',op='lte',value=2020)
        self.assertEqual([score(y,[low,high]) for y in (2000,2010,2020)],[0,0.5,1])
        for filters in ([low],[high]):
            values=[score(y,filters) for y in (2000,2010,2020)]
            self.assertTrue(0<=values[0]<values[1]<values[2]<=1)
        self.assertEqual(score(2000,[low,dict(field='startYear',op='lte',value=2000)]),1)

    def test_custom_score_settings(self):
        filters=[dict(field='genres',op='any_of',value=['Sci-Fi']),dict(field='averageRating',op='gte',value=7)]
        settings={'weights':{'genres':3,'averageRating':1,'search':0},'genrePenalty':0,'ratingPower':2}
        row=get(q='tt1375666',filters=filters,scoring=settings)['rows'][0]
        self.assertAlmostEqual(row['filterScore'],(3*100+77.44)/4,delta=0.1)
        settings['genrePenalty']=2
        penalized=get(q='tt1375666',filters=filters,scoring=settings)['rows'][0]
        self.assertLess(penalized['filterScore'],row['filterScore'])
        settings['weights']={'genres':0,'averageRating':0,'search':0}
        self.assertIsNone(get(q='tt1375666',filters=filters,scoring=settings)['rows'][0]['filterScore'])
        with self.assertRaises(ValueError): get(scoring={'weights':{'genres':-1}})
        with self.assertRaises(ValueError): get(scoring={'votesCap':0})

    def test_score_components_and_weights(self):
        def parts(row,filters):
            components=score_components(filters)
            with sqlite3.connect(':memory:') as db:
                db.create_function('LOG10PLUS',1,lambda n:math.log10(n+1))
                db.create_function('SCOREPOWER',2,lambda v,p:v**p)
                sql='SELECT '+','.join(c['sql'] for c in components)+' FROM (SELECT '+','.join('? AS '+k for k in row)+')'
                return db.execute(sql,[v for c in components for v in c['args']]+list(row.values())).fetchone()
        genre=[dict(field='genres',op='any_of',value=['Comedy','Drama'])]
        self.assertEqual(parts({'genres':'Comedy'},genre),(0.5,))
        self.assertEqual(parts({'genres':'Comedy,Drama'},genre),(1.0,))
        self.assertAlmostEqual(parts({'genres':'Comedy,Drama,Horror'},genre)[0],2/3)
        self.assertAlmostEqual(parts({'genres':'Comedy,Horror'},genre)[0],1/3)
        self.assertEqual(parts({'genres':'Horror'},genre),(0.0,))
        self.assertEqual(parts({'genres':None},genre),(0.0,))
        rating=[dict(field='averageRating',op='gte',value=7)]
        self.assertGreater(parts({'averageRating':9},rating)[0],parts({'averageRating':8},rating)[0])
        votes=[dict(field='numVotes',op='gte',value=100)]
        self.assertGreater(parts({'numVotes':10000},votes)[0],parts({'numVotes':100},votes)[0])
        years=[dict(field='startYear',op='gte',value=2000),dict(field='startYear',op='lte',value=2020)]
        self.assertEqual(parts({'startYear':2010},years),(1.0,))
        self.assertEqual(parts({'startYear':2000},years),(0.5,))
        self.assertEqual(len(score_components(years)),1)

    def test_score_ranking_is_global_and_optional(self):
        self.assertTrue(all(r['filterScore'] is None for r in get(sort='filterScore')['rows']))
        filters=[dict(field='genres',op='any_of',value=['Comedy','Drama']),dict(field='averageRating',op='gte',value=7),dict(field='numVotes',op='gte',value=10000)]
        first=get(filters=filters,sort='filterScore',size=25)
        second=get(filters=filters,sort='filterScore',size=25,page=2)
        self.assertEqual(first['total'],get(filters=filters)['total'])
        rows=first['rows']+second['rows']
        scores=[r['filterScore'] for r in rows]
        self.assertEqual(scores,sorted(scores,reverse=True))
        self.assertEqual(len({r['tconst'] for r in rows}),50)
        self.assertTrue(all(0<=s<=100 for s in scores))
        for row in rows:
            self.assertAlmostEqual(row['filterScore'],sum(p['score'] for p in row['scoreBreakdown'])/3,delta=0.11)

    def test_total_and_page_boundaries(self):
        first=get(size=25)
        second=get(size=25,page=2)
        self.assertEqual(first['total'],756513)
        self.assertEqual(len(first['rows']),25)
        self.assertFalse({r['tconst'] for r in first['rows']} & {r['tconst'] for r in second['rows']})
        last=get(size=250,page=99999999)
        self.assertEqual(last['page'],last['pages'])
        self.assertEqual(len(last['rows']),756513 % 250)

    def test_all_columns_sort_in_both_directions(self):
        for column,_,kind in COLUMNS:
            for direction in ['asc','desc']:
                result=get(sort=column,direction=direction,size=25)
                self.assertEqual(len(result['rows']),25)
                if kind in ['number','boolean']:
                    values=[r[column] for r in result['rows'] if r[column] is not None]
                    self.assertEqual(values,sorted(values,reverse=direction=='desc'))

    def test_combined_filters(self):
        filters=[dict(field='averageRating',op='gte',value=8),dict(field='numVotes',op='gte',value=10000),dict(field='startYear',op='gte',value=1990),dict(field='startYear',op='lte',value=2000),dict(field='genres',op='has',value='Drama'),dict(field='isAdult',op='eq',value='0')]
        result=get(filters=filters)
        self.assertGreater(result['total'],0)
        for r in result['rows']:
            self.assertGreaterEqual(r['averageRating'],8)
            self.assertGreaterEqual(r['numVotes'],10000)
            self.assertTrue(1990<=r['startYear']<=2000)
            self.assertIn('Drama',r['genres'].split(','))
            self.assertEqual(r['isAdult'],0)

    def test_missing_ratings_preserved(self):
        missing=get(filters=[dict(field='averageRating',op='missing')])
        present=get(filters=[dict(field='averageRating',op='present')])
        self.assertEqual(missing['total']+present['total'],756513)
        self.assertEqual(present['total'],348202)
        self.assertTrue(all(r['averageRating'] is None for r in missing['rows']))

    def test_multiple_genres_any_and_all(self):
        base=[dict(field='numVotes',op='gte',value=10000)]
        any_result=get(filters=base+[dict(field='genres',op='any_of',value=['Comedy','Drama'])])
        all_result=get(filters=base+[dict(field='genres',op='all_of',value=['Comedy','Drama'])])
        self.assertGreater(any_result['total'],all_result['total'])
        self.assertGreater(all_result['total'],0)
        for row in any_result['rows']:
            self.assertTrue({'Comedy','Drama'} & set(row['genres'].split(',')))
            self.assertGreaterEqual(row['numVotes'],10000)
        for row in all_result['rows']:
            self.assertTrue({'Comedy','Drama'} <= set(row['genres'].split(',')))
        with self.assertRaises(ValueError):
            get(filters=[dict(field='genres',op='any_of',value='Drama')])
        with self.assertRaises(ValueError):
            get(filters=[dict(field='genres',op='all_of',value=[])])

    def test_id_search_and_empty_state(self):
        result=get(q='tt0111161')
        self.assertEqual(result['total'],1)
        self.assertEqual(result['rows'][0]['primaryTitle'],'The Shawshank Redemption')
        self.assertEqual(result['rows'][0]['averageRating'],9.3)
        self.assertEqual(get(q="' OR 1=1; --")['total'],0)
        self.assertEqual(get(filters=[dict(field='genres',op='has',value='Dram')])['total'],0)

    def test_invalid_query_rejected(self):
        for kwargs in [dict(sort='invalid'),dict(direction='invalid'),dict(size=100000),dict(filters=[dict(field='averageRating',op='gte',value='NaN')]),dict(filters=[dict(field='invalid',op='eq',value=1)])]:
            with self.assertRaises(ValueError): get(**kwargs)

if __name__=='__main__': unittest.main()
