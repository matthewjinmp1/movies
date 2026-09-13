import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import blocked
import seen
import starred
from server import query


class BlockedTests(unittest.TestCase):
    def test_block_unblock_and_view_counts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(blocked, 'PATH', Path(directory)/'blocked.json'), patch.object(seen, 'PATH', Path(directory)/'seen.json'), patch.object(starred, 'PATH', Path(directory)/'starred.json'):
            movie = 'tt1375666'
            seen.update(movie, True)
            starred.update(movie, True)
            self.assertEqual(query({'q':[movie]})['total'], 1)
            blocked.update(movie, True)
            blocked.update(movie, True)
            for view in ['all', 'starred', 'seen']:
                self.assertEqual(query({'view':[view], 'q':[movie]})['total'], 0)
            result = query({'view':['blocked'], 'page':['999']})
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['page'], 1)
            self.assertEqual(result['blockedCount'], 1)
            self.assertTrue(result['rows'][0]['blocked'])
            self.assertEqual(query({'view':['blocked'], 'q':['nonexistent movie xyz']})['total'], 0)
            blocked.update(movie, False)
            self.assertEqual(query({'view':['blocked']})['total'], 0)
            for view in ['all', 'starred', 'seen']:
                self.assertEqual(query({'view':[view], 'q':[movie]})['total'], 1)
            with self.assertRaises(ValueError): blocked.update('bad', True)
            self.assertEqual(blocked.read(), set())
