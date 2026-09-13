import json
import unittest
from unittest.mock import patch
import enrichment
import global_scoring
import preferences
import server
from scoring import score_components

class EnrichmentTests(unittest.TestCase):
    def test_flatten_missing_and_native_scales(self):
        row=enrichment.flatten({'data':{'ratings':[{'source':'letterboxd','value':3.9,'votes':120}], 'budget':0,'keywords':[{'name':'time, travel'}]}})
        self.assertEqual(row['letterboxd'],3.9)
        self.assertIsNone(row['rtCritic'])
        self.assertIsNone(row['budget'])
        self.assertEqual(json.loads(row['keywords']),['time, travel'])

    def test_filters_sort_and_missing_rows(self):
        with patch('server.blocked.read',return_value=set()), patch('server.seen.read',return_value=set()):
            params={'q':['tt20215234'],'filters':[json.dumps([{'field':'rtCritic','op':'gte','value':90}])], 'sort':['rtCritic']}
            result=server.query(params)
            self.assertEqual(result['total'],1)
            self.assertEqual(result['rows'][0]['rtCritic'],93)
            self.assertEqual(result['rows'][0]['filterScore'],96.5)
            keyword=result['rows'][0]['keywords'][0]
            params['filters']=[json.dumps([{'field':'keywords','op':'all_of','value':[keyword]}])]
            self.assertEqual(server.query(params)['total'],1)
            params['filters']=[json.dumps([{'field':'rtCritic','op':'missing'}])]
            self.assertEqual(server.query(params)['total'],0)
            missing=server.query({'filters':[json.dumps([{'field':'mdbAvailable','op':'eq','value':'0'}])],'size':['25']})
            self.assertTrue(all(r['rtCritic'] is None for r in missing['rows']))

    def test_global_migration_and_preferences(self):
        old=global_scoring.validate()
        for key in enrichment.NUMERIC:
            del old['weights'][key];del old['fields'][key]
        migrated=global_scoring.validate(old)
        self.assertEqual(migrated['weights']['rtCritic'],0)
        migrated['weights']['rtCritic']=3
        self.assertEqual(global_scoring.mapping('rtCritic',[(50,1),(100,1),(None,100)],migrated),{50:50,100:100,None:0})
        data=preferences.read()
        data['visibleFilters']=['rtCritic','keywords','mdbAvailable']
        data['values'].update(rtCritic={'min':'80','max':'','status':'present'},keywords={'values':['mystery'],'mode':'any_of'},mdbAvailable={'value':'1'})
        self.assertEqual(preferences.validate(data)['values']['rtCritic']['min'],'80')
