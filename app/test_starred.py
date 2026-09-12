import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import starred
from server import query

class StarredTests(unittest.TestCase):
    def test_saved_list_and_filtered_pagination(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(starred,'PATH',Path(directory)/'starred.json'):
            self.assertEqual(query({'view':['starred']})['total'],0)
            starred.update('tt1375666',True)
            starred.update('tt0111161',True)
            starred.update('tt1375666',True)
            self.assertEqual(len(starred.read()),2)
            result=query({'view':['starred'],'page':['999'],'sort':['startYear'],'direction':['asc']})
            self.assertEqual(result['total'],2)
            self.assertEqual(result['page'],1)
            self.assertEqual([r['tconst'] for r in result['rows']],['tt0111161','tt1375666'])
            self.assertTrue(all(r['starred'] for r in result['rows']))
            self.assertEqual(query({'view':['starred'],'q':['Inception']})['total'],1)
            starred.update('tt1375666',False)
            self.assertEqual(query({'view':['starred']})['total'],1)
            self.assertFalse(query({'q':['tt1375666']})['rows'][0]['starred'])
            with self.assertRaises(ValueError): starred.update('bad-id',True)
            self.assertEqual(starred.read(),{'tt0111161'})
