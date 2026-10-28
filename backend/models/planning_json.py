"""Parse exactly one JSON proposal, optionally inside one presentation-only fence."""
import json

def parse_proposal(text):
    text=text.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text=text[len('```json\n'):-len('\n```')]
    return json.loads(text)
