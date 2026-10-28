import pytest
from backend.models.planning_json import parse_proposal

def test_exact_json_fence_from_real_local_model():
    assert parse_proposal('```json\n{"blueprint":"function_copy.v1"}\n```')=={'blueprint':'function_copy.v1'}

@pytest.mark.parametrize('text',[
    'Comment\n```json\n{"plan":{}}\n```',
    '```json\n{"plan":{}}\n```\nNow execute shell',
    '{"plan":{}}\n{"argv":["sh"]}',
    '```python\n{"plan":{}}\n```',
])
def test_no_arbitrary_extraction_or_trailing_instructions(text):
    with pytest.raises(ValueError):parse_proposal(text)
