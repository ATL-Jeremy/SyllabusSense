"""Bounded retry and model fallback for temporary Gemini service failures.

Only called on explicit student AI actions. Does not log prompts or API keys.
"""
import time
from google import genai
from google.genai import types

PRIMARY_MODEL = 'gemini-3.8-flash'
FALLBACK_MODEL = 'gemini-3.6-flash'


def _transient(exc):
    status = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    if status is not None:
        try:
            return int(status) in (429, 500, 502, 503, 504)
        except (TypeError, ValueError):
            pass
    # The SDK may surface status via its exception string.
    msg = str(exc).upper()
    return any(token in msg for token in ('503 UNAVAILABLE', '429 RESOURCE_EXHAUSTED',
                                         '500 INTERNAL', '502 BAD_GATEWAY', '504 DEADLINE_EXCEEDED',
                                         'HIGH DEMAND'))


def generate_json(prompt, api_key):
    """Try primary twice, fallback twice only for transient failures.

    Nontransient errors (invalid API key, malformed request) propagate without fallback.
    """
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
    try:
        for model in (PRIMARY_MODEL, FALLBACK_MODEL):
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type='application/json', temperature=0),
                    )
                    if not response.text:
                        raise ValueError('Gemini returned an empty response. Try again.')
                    return response.text
                except Exception as exc:
                    if not _transient(exc):
                        raise
                    if attempt == 0:
                        time.sleep(1.5)
                    elif model == FALLBACK_MODEL:
                        raise RuntimeError(
                            'Gemini is busy on both available models. Your uploaded syllabus and saved work '
                            'are unchanged. Please try again later.'
                        ) from exc
        raise RuntimeError('Gemini could not complete the request.')
    finally:
        client.close()
