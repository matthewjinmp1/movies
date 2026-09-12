import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import seen
from server import query


class SeenTests(unittest.TestCase):
    def test_seen_list_and_filtered_pagination(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(seen, 'PATH', Path(directory) / 'seen.json'):
            self.assertEqual(query({'view': ['seen']})['total'], 0)
            seen.update('tt1375666', True)
            seen.update('tt0111161', True)
            seen.update('tt1375666', True)
            self.assertEqual(len(seen.read()), 2)
            result = query({'view': ['seen'], 'page': ['999'], 'sort': ['startYear'], 'direction': ['asc']})
            self.assertEqual(result['total'], 2)
            self.assertEqual(result['page'], 1)
            self.assertEqual([r['tconst'] for r in result['rows']], ['tt0111161', 'tt1375666'])
            self.assertTrue(all(r['seen'] for r in result['rows']))
            self.assertEqual(query({'view': ['seen'], 'q': ['Inception']})['total'], 1)
            seen.update('tt1375666', False)
            self.assertEqual(query({'view': ['seen']})['total'], 1)
            self.assertFalse(query({'q': ['tt1375666']})['rows'][0]['seen'])
            with self.assertRaises(ValueError): seen.update('bad-id', True)
            self.assertEqual(seen.read(), {'tt0111161'})


if __name__ == '__main__':
    unittest.main()
