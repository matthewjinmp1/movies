import tempfile
import unittest
from unittest.mock import patch
import preferences
from pathlib import Path
from preferences import read, save

class PreferenceTests(unittest.TestCase):
    def test_view_paths_keep_existing_all_filters(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(preferences,'PATH',Path(directory)/'filters.json'):
            self.assertEqual(preferences.view_path('all'),Path(directory)/'filters.json')
            paths=[preferences.view_path(view) for view in ('all','seen','starred','blocked')]
            self.assertEqual(len(set(paths)),4)
            with self.assertRaises(ValueError):preferences.view_path('../other')

    def test_roundtrip_clear_and_rejected_write(self):
        data=dict(version=1,q='Matrix',visibleFilters=['genres','averageRating'],values={
            'genres':dict(values=['Action','Sci-Fi'],mode='any_of'),
            'averageRating':dict(min='7.5',status='rated'),
            'numVotes':dict(min='10000'),'startYear':dict(min='1990',max='2020'),
            'runtimeMinutes':dict(min='',max='150'),'isAdult':dict(value='0')})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'filters.json'
            self.assertIsNone(read(path))
            save(data,path)
            self.assertEqual(read(path),data)
            with self.assertRaises(ValueError): save({'version':99},path)
            self.assertEqual(read(path),data)
            data['q']='';data['values']['genres']['values']=[]
            save(data,path)
            self.assertEqual(read(path),data)
            data['scoring']={'weights':{'genres':3},'genrePenalty':2}
            save(data,path)
            self.assertEqual(read(path)['scoring']['weights']['genres'],3)
            self.assertEqual(read(path)['scoring']['genrePenalty'],2)

if __name__=='__main__': unittest.main()
