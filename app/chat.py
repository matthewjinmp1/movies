"""Small server-side OpenRouter chat client for the movie browser."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = 'https://openrouter.ai/api/v1/chat/completions'
MODEL = 'deepseek/deepseek-v4-flash-0731'
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 8000
MAX_RESPONSE_TOKENS = 2000
MAX_ATTEMPTS = 3
RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
ROOT = Path(__file__).resolve().parent


def load_local_env():
    """Load simple KEY=VALUE entries without overwriting the shell environment."""
    path = ROOT.parent / '.env'
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if value[:1] in ('"', "'") and value[-1:] == value[:1]:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def validate_messages(messages):
    if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
        raise ValueError(f'Enter between 1 and {MAX_MESSAGES} messages.')
    result = []
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
            raise ValueError('Invalid chat message.')
        content = message.get('content')
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            raise ValueError(f'Each message must be 1–{MAX_MESSAGE_CHARS:,} characters.')
        result.append({'role': message['role'], 'content': content})
    if result[0]['role'] != 'user' or result[-1]['role'] != 'user':
        raise ValueError('A chat request must start and end with a user message.')
    return result


def response_text(payload):
    if not isinstance(payload, dict):
        raise RuntimeError('OpenRouter returned an invalid response.')
    error = payload.get('error')
    if isinstance(error, dict):
        raise RuntimeError(str(error.get('message') or 'OpenRouter returned an error.'))
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError('OpenRouter returned no response.')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text = ''.join(part.get('text', '') for part in content if isinstance(part, dict)).strip()
        if text:
            return text
    raise RuntimeError('OpenRouter returned an empty response.')


def complete(messages):
    load_local_env()
    api_key = os.environ.get('OPENROUTER_KEY') or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        raise RuntimeError('OPENROUTER_KEY is not set. Add it to .env or your shell environment.')
    messages = validate_messages(messages)
    payload = json.dumps({
        'model': MODEL,
        'messages': messages,
        'max_tokens': MAX_RESPONSE_TOKENS,
        'temperature': 0.7,
        # This is a simple chat UI; do not request provider reasoning tokens that
        # can consume the completion budget without producing final content.
        'reasoning': {'enabled': False},
    }).encode('utf-8')
    request = urllib.request.Request(API_URL, data=payload, method='POST', headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:3002',
        'X-Title': 'Frame Movie Library',
    })
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
                result = json.loads(body.decode('utf-8'))
            try:
                return response_text(result)
            except RuntimeError as error:
                last_error = error
                if attempt == MAX_ATTEMPTS:
                    raise
        except urllib.error.HTTPError as error:
            last_error = error
            try:
                details = json.loads(error.read().decode('utf-8'))
                message = details.get('error', {}).get('message') if isinstance(details, dict) else None
            except (ValueError, UnicodeDecodeError):
                message = None
            if error.code not in RETRYABLE_HTTP_STATUS or attempt == MAX_ATTEMPTS:
                raise RuntimeError(message or f'OpenRouter request failed (HTTP {error.code}).') from error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f'Could not reach OpenRouter: {error.reason if hasattr(error, "reason") else error}') from error
        time.sleep(attempt * 1.5)
    raise RuntimeError(f'OpenRouter request failed: {last_error}')
