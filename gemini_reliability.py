"""Quota-aware Gemini calls for SyllabusSense.

Runs only when the user explicitly requests AI. Never logs keys or student content.
A process-local quota cooldown avoids repeatedly spending calls on exhausted models.
"""
import re
import time
from google import genai
from google.genai import types

PRIMARY_MODEL = 'gemini-3.8-flash'
FALLBACK_MODEL = 'gemini-3.6-flash'
_MODELS = (PRIMARY_MODEL, FALLBACK_MODEL)
_BLOCKED_UNTIL = {}


class GeminiQuotaError(RuntimeError):
    """API quota is exhausted or request-rate limited; no retry should occur."""


def _status(exc):
    raw = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    try:
        return int(raw)
    except (ValueError, TypeError):
        match = re.search(r'\b(429|500|502|503|504)\b', str(exc))
        return int(match.group(1)) if match else None


def _transient(exc):
    return _status(exc) in (500, 502, 503, 504)


def _retry_seconds(exc):
    """Read retry hint without exposing the underlying error to students."""
    msg = str(exc)
    match = re.search(r'Please retry in\s+(?:(\d+)h)?(?:(\d+)m)?([\d.]+)s', msg, re.I)
    if match:
        return int(match.group(1) or 0)*3600 + int(match.group(2) or 0)*60 + float(match.group(3))
    match = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", msg)
    if match:
        return float(match.group(1))
    return None


def _quota_message(wait=None):
    if wait is None:
        return ('Gemini API request limit reached. Google has not provided a retry time. '
                'Your uploaded syllabus and saved work are unchanged. You can keep using the manual tools.')
    minutes = max(1, int((wait + 59) // 60))
    if minutes >= 60:
        duration = f'{minutes // 60}h {minutes % 60}m'
    else:
        duration = f'{minutes} minutes'
    return (f'Gemini API request limit reached. Google suggests retrying in approximately {duration}. '
            'Your uploaded syllabus and saved work are unchanged. You can keep using the manual tools.')


def _cooldown(model, exc):
    delay = _retry_seconds(exc)
    # Conservative fallback when quota response has no retry hint.
    _BLOCKED_UNTIL[model] = time.monotonic() + (delay if delay is not None else 60)


def _request(contents, api_key, config=None):
    now = time.monotonic()
    available = [model for model in _MODELS if _BLOCKED_UNTIL.get(model, 0) <= now]
    if not available:
        wait = min(_BLOCKED_UNTIL.values()) - now
        raise GeminiQuotaError(_quota_message(wait))

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
    quota_failures = 0
    temporary_failures = 0
    try:
        for model in available:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(model=model, contents=contents, config=config)
                    if not response.text:
                        raise ValueError('Gemini returned an empty response; please try again.')
                    return response.text
                except Exception as exc:
                    if _status(exc) == 429:
                        _cooldown(model, exc)
                        quota_failures += 1
                        break  # Do NOT retry a quota-exhausted model.
                    if not _transient(exc):
                        raise
                    temporary_failures += 1
                    if attempt == 0:
                        time.sleep(1.5)
                    else:
                        break
        if quota_failures and not temporary_failures:
            blocked = [max(0, _BLOCKED_UNTIL.get(m, 0) - time.monotonic()) for m in _MODELS]
            wait = min(blocked) if all(blocked) else None
            raise GeminiQuotaError(_quota_message(wait))
        raise RuntimeError('Gemini is temporarily unavailable. Your saved work is unchanged; try again later.')
    finally:
        client.close()


def generate_json(prompt, api_key):
    return _request(prompt, api_key, types.GenerateContentConfig(
        response_mime_type='application/json', temperature=0))


def generate_transcript(audio, api_key):
    if not audio or len(audio) > 4*1024*1024:
        raise ValueError('Record a short audio clip (under 4 MB).')
    return _request([
        'Transcribe these spoken notes verbatim, as plain text. Do not infer dates, summarize, or add words.',
        types.Part.from_bytes(data=audio, mime_type='audio/wav')
    ], api_key).strip()[:2000]
