import json
import pytest
from backend.runtime.screen_region import validate_guide


def test_visual_guide_validates_advisory_marks():
    value={'answer':'Select the visible button','annotations':[{'x':10,'y':20,'w':20,'h':10,'label':'Button'}]}
    assert validate_guide(json.dumps(value))==value


@pytest.mark.parametrize('mark',[{'x':90,'y':10,'w':20,'h':10,'label':'Outside'},
    {'x':True,'y':0,'w':5,'h':5,'label':'Invalid'},
    {'x':0,'y':0,'w':5,'h':5,'label':'Invalid','click':True}])
def test_reject_invalid_or_executable_annotations(mark):
    with pytest.raises(ValueError):validate_guide(json.dumps({'answer':'Guide','annotations':[mark]}))
