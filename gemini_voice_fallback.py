"""Explicit-consent short audio transcription; no recordings are stored."""
from gemini_reliability import generate_transcript


def transcribe_audio(audio, api_key):
    transcript = generate_transcript(audio, api_key)
    if not transcript:
        raise ValueError('No speech was recognized; try again or type your clues.')
    return transcript
