import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import global_scoring
import rating_insights as insights
import ratings
from server import COLUMNS, connect


class RatingInsightTests(unittest.TestCase):
    def test_rank_correlation_and_p_values(self):
        self.assertEqual(insights.ranks([3, 1, 3, 2]), [2.5, 0, 2.5, 1])
        self.assertAlmostEqual(insights.pearson([1, 2, 3], [2, 4, 6]), 1)
        self.assertLess(insights.p_value(0.6, 32), 0.01)
        self.assertGreater(insights.p_value(0.1, 32), 0.5)

    def test_correlations_cover_stats_and_genres(self):
        movies = {'tt0111161':9, 'tt0068646':9, 'tt1375666':8, 'tt0468569':7, 'tt0109830':4, 'tt0133093':3, 'tt0816692':6}
        with tempfile.TemporaryDirectory() as directory, patch.object(ratings, 'PATH', Path(directory)/'ratings.json'):
            for movie, rating in movies.items():
                ratings.update(movie, rating)
            with closing(connect(my_ratings=ratings.read())) as db:
                global_scoring.attach(db)
                result = insights.correlations(db, COLUMNS)
        self.assertEqual(result['ratings'], 7)
        labels = {s['label'] for s in result['stats']}
        self.assertIn('IMDb rating', labels)
        self.assertNotIn('My rating', labels)
        self.assertTrue(any(s['group'] == 'Genre' for s in result['stats']))
        strengths = [abs(s['spearman']) for s in result['stats']]
        self.assertEqual(strengths, sorted(strengths, reverse=True))
        self.assertTrue(all(0 <= s['q'] <= 1 and s['q'] >= s['p'] for s in result['stats']))


if __name__ == '__main__':
    unittest.main()
