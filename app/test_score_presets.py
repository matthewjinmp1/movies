import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import score_presets as presets
import global_scoring

class PresetTests(unittest.TestCase):
    def test_named_snapshots_and_updates(self):
        with tempfile.TemporaryDirectory() as d, patch.object(presets,'PATH',Path(d)/'presets.json'):
            first=global_scoring.validate();second=global_scoring.validate();second['weights']['genres']=7
            rows=presets.change(dict(action='save',name='First',settings=first));ident=rows[0]['id']
            presets.change(dict(action='save',name='Second',settings=second))
            self.assertEqual([r['settings']['weights']['genres'] for r in presets.read()],[1,7])
            with self.assertRaises(ValueError):presets.change(dict(action='save',name='First',settings=second))
            presets.change(dict(action='update',id=ident,name='Renamed',settings=second))
            self.assertEqual(presets.read()[0]['name'],'Renamed')
            presets.change(dict(action='delete',id=ident))
            self.assertEqual(presets.read()[0]['name'],'Second')
