import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ratings
from server import query


class RatingTests(unittest.TestCase):
    def test_ratings_saved_sorted_and_cleared(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(ratings, 'PATH', Path(directory) / 'ratings.json'):
            ratings.update('tt1375666', 8)
            ratings.update('tt0111161', 10.0)
            ratings.update('tt0068646', 0)
            self.assertEqual(ratings.read(), {'tt1375666':8, 'tt0111161':10, 'tt0068646':0})
            rows = query({'sort':['myRating'], 'direction':['desc'], 'size':['25']})['rows']
            self.assertEqual([r['myRating'] for r in rows[:4]], [10, 8, 0, None])
            self.assertEqual(query({'sort':['myRating'], 'direction':['asc']})['rows'][0]['tconst'], 'tt0068646')
            self.assertEqual(query({'q':['tt1375666'], 'sort':['globalScore'], 'direction':['desc']})['rows'][0]['myRating'], 8)
            ratings.update('tt1375666', None)
            self.assertNotIn('tt1375666', ratings.read())
            for bad in (11, -1, 7.5, True, '5', float('nan')):
                with self.assertRaises(ValueError): ratings.update('tt0111161', bad)
            with self.assertRaises(ValueError): ratings.update('bad-id', 50)
            with self.assertRaises(ValueError): query({'filters':['[{"field":"myRating","op":"gte","value":50}]']})


if __name__ == '__main__':
    unittest.main()
