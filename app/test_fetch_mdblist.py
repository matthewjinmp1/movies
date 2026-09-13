import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_mdblist as fetch


class DownloadTests(unittest.TestCase):
    def test_full_response_saved_and_resume_skips_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fetch.save(root/'selection.json', {'movies':[{'tconst':'tt123','primaryTitle':'Test'}]})
            response = io.BytesIO(json.dumps({'ids':{'imdb':'tt123'},'ratings':[{'source':'tomatoes','value':88}], 'extra':{'example':True}}).encode())
            response.headers = {}
            with patch.object(fetch,'DIRECTORY',root), patch.object(fetch.chat,'load_local_env'), patch.dict(fetch.os.environ,{'MDBList_KEY':'test'}), patch.object(sys,'argv',['fetch_mdblist.py']), patch.object(fetch.time,'sleep'), patch.object(fetch.urllib.request,'urlopen',return_value=response) as request:
                fetch.main()
                fetch.main()
                self.assertEqual(request.call_count,1)
            saved = json.loads((root/'tt123.json').read_text())
            self.assertTrue(saved['data']['extra']['example'])
            self.assertEqual(json.loads((root/'summary.json').read_text())['remaining'],0)
