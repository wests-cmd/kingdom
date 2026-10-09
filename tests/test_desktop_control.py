import os
import pytest
from backend.runtime.desktop_control import validate_input, desktop_input


@pytest.mark.parametrize('parameters',[
    {'action':'click','window_title':'Test','x':-1,'y':10},
    {'action':'click','window_title':'Test','x':True,'y':10},
    {'action':'type_text','window_title':'Test','text':'execute\n'},
    {'action':'type_text','window_title':'Test','text':'x'*4001},
    {'action':'key','window_title':'Test','key':'win+r'},
    {'action':'key','window_title':'','key':'enter'},
    {'action':'unknown','window_title':'Test'},
])
def test_invalid_desktop_action_rejected_before_input(parameters):
    with pytest.raises(ValueError):validate_input(parameters)


def test_desktop_rejects_unavailable_platform_or_wrong_foreground_without_input():
    parameters={'action':'type_text','window_title':'KINGDOM TEST WINDOW THAT DOES NOT EXIST 67b85d','text':'must never be typed'}
    with pytest.raises(PermissionError if os.name=='nt' else RuntimeError):desktop_input(parameters)


def test_desktop_input_accepts_only_explicit_parameters():
    for parameters in [
        {'action':'type_text','window_title':'Test','text':'printable text'},
        {'action':'click','window_title':'Test','x':12,'y':25},
        {'action':'key','window_title':'Test','key':'ctrl+s'}]:
        assert validate_input(parameters)==parameters
