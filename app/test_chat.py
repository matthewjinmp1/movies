import unittest
from unittest import mock
import chat


class ChatTests(unittest.TestCase):
    def test_validate_messages(self):
        messages = chat.validate_messages([
            {'role': 'user', 'content': 'hello'},
            {'role': 'assistant', 'content': 'hi'},
            {'role': 'user', 'content': 'recommend a movie'},
        ])
        self.assertEqual(messages[-1]['role'], 'user')
        with self.assertRaises(ValueError): chat.validate_messages([])
        with self.assertRaises(ValueError): chat.validate_messages([{'role': 'assistant', 'content': 'hi'}])
        with self.assertRaises(ValueError): chat.validate_messages([{'role': 'user', 'content': 'x' * 8001}])

    def test_response_text(self):
        self.assertEqual(chat.response_text({'choices': [{'message': {'content': ' hello '}}]}), 'hello')
        self.assertEqual(chat.response_text({'choices': [{'message': {'content': [{'text': 'one'}, {'text': ' two'}]}}]}), 'one two')
        with self.assertRaises(RuntimeError): chat.response_text({'choices': []})

    def test_complete_uses_server_key_and_model(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return b'{"choices":[{"message":{"content":"answer"}}]}'

        with mock.patch.dict(chat.os.environ, {'OPENROUTER_KEY': 'test-key'}, clear=False), \
             mock.patch.object(chat.urllib.request, 'urlopen', return_value=Response()) as urlopen:
            self.assertEqual(chat.complete([{'role': 'user', 'content': 'hello'}]), 'answer')
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, chat.API_URL)
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')
        self.assertIn(chat.MODEL.encode(), request.data)
