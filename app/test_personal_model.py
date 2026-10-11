import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import personal_model as model
import ratings
from server import query


class PersonalModelTests(unittest.TestCase):
    def test_fit_learns_genre_taste_and_keeps_quality_baseline(self):
        pool = [(f'tt{i}', 'Horror' if i % 2 else 'Drama', 7.5, None) for i in range(1, 13)]
        pool += [('tt100', 'Horror', 8.5, None), ('tt101', 'Horror', 5.5, None), ('tt102', 'Drama', 7.5, None)]
        rated = {f'tt{i}': 9 if i % 2 else 5 for i in range(1, 13)}
        predictions, summary = model.fit(rated, pool)
        self.assertEqual(summary['ratings'], 12)
        self.assertGreater(predictions['tt100'], predictions['tt102'])
        self.assertAlmostEqual(predictions['tt100'] - predictions['tt101'], 1.5, places=1)
        self.assertEqual(summary['genreEffects'][0][0], 'Horror')
        self.assertLess(summary['heldOutError'], summary['averageGuessError'])
        self.assertEqual(model.fit(dict(list(rated.items())[:4]), pool)[0], {})

    def test_query_sorts_by_prediction_and_reports_model(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(ratings, 'PATH', Path(directory)/'ratings.json'), patch.object(model, 'CACHE', Path(directory)/'personal.sqlite3'):
            for movie, rating in {'tt0111161':9, 'tt0068646':9, 'tt1375666':8, 'tt0468569':7, 'tt0109830':4, 'tt0133093':3}.items():
                ratings.update(movie, rating)
            result = query({'sort':['predictedRating'], 'direction':['desc'], 'size':['50']})
            values = [row['predictedRating'] for row in result['rows']]
            self.assertEqual(values, sorted(values, reverse=True))
            self.assertTrue(all(v is not None for v in values))
            self.assertEqual(result['prediction']['ratings'], 6)
            ascending = query({'sort':['predictedRating'], 'direction':['asc']})['rows'][0]['predictedRating']
            self.assertLessEqual(ascending, values[-1])
            single = query({'q':['tt0111161'], 'sort':['predictedRating'], 'direction':['desc'], 'page':['2']})
            self.assertEqual(single['rows'][0]['tconst'], 'tt0111161')
            with self.assertRaises(ValueError):
                query({'filters':[json.dumps([{'field':'predictedRating','op':'gte','value':5}])]})
            ratings.update('tt0133093', None)
            self.assertEqual(query({'q':['tt0111161']})['prediction']['ratings'], 5)


if __name__ == '__main__':
    unittest.main()
