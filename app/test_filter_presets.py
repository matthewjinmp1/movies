import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import filter_presets as presets

class FilterPresetTests(unittest.TestCase):
    def test_presets_remain_after_clearing_current_filters(self):
        values={'genres':{'values':[],'mode':'any_of'},'averageRating':{'min':'','status':'any'},'numVotes':{'min':'100000'},'startYear':{'min':'','max':''},'runtimeMinutes':{'min':'','max':''},'isAdult':{'value':''},'notSeen':{}}
        settings=dict(version=1,q='',visibleFilters=['numVotes','notSeen'],values=values)
        with tempfile.TemporaryDirectory() as d,patch.object(presets,'PATH',Path(d)/'presets.json'):
            rows=presets.change(dict(action='save',name='Unseen',settings=settings));ident=rows[0]['id']
            settings['visibleFilters']=[]
            self.assertEqual(presets.read()[0]['settings']['visibleFilters'],['numVotes','notSeen'])
            presets.change(dict(action='save',name='Everything',settings=settings))
            with self.assertRaises(ValueError):presets.change(dict(action='save',name='Unseen',settings=settings))
            presets.change(dict(action='delete',id=ident))
            self.assertEqual(presets.read()[0]['name'],'Everything')
