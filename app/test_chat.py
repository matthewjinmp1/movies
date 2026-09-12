import io
import unittest
import urllib.error
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

    def test_retryable_statuses_are_configured(self):
        self.assertIn(502, chat.RETRYABLE_HTTP_STATUS)
        self.assertNotIn(401, chat.RETRYABLE_HTTP_STATUS)

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

    def test_complete_retries_transient_provider_failure(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return b'{"choices":[{"message":{"content":"recovered"}}]}'

        transient = urllib.error.HTTPError(
            chat.API_URL, 502, 'bad gateway', {},
            io.BytesIO(b'{"error":{"message":"temporary provider error"}}'),
        )
        with mock.patch.dict(chat.os.environ, {'OPENROUTER_KEY': 'test-key'}, clear=False), \
             mock.patch.object(chat.urllib.request, 'urlopen', side_effect=[transient, Response()]) as urlopen, \
             mock.patch.object(chat.time, 'sleep'):
            self.assertEqual(chat.complete([{'role': 'user', 'content': 'hello'}]), 'recovered')
        self.assertEqual(urlopen.call_count, 2)

    def test_complete_retries_empty_final_content(self):
        class Response:
            def __init__(self, content): self.content = content
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return ('{"choices":[{"message":{"content":"' + self.content + '"}}]}').encode()

        with mock.patch.dict(chat.os.environ, {'OPENROUTER_KEY': 'test-key'}, clear=False), \
             mock.patch.object(chat.urllib.request, 'urlopen', side_effect=[Response(''), Response('recovered')]) as urlopen, \
             mock.patch.object(chat.time, 'sleep'):
            self.assertEqual(chat.complete([{'role': 'user', 'content': 'hello'}]), 'recovered')
        self.assertEqual(urlopen.call_count, 2)
