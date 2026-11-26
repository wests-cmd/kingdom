import json
from types import SimpleNamespace
import platform
import pytest
from backend.runtime import desktop_observation as observer


class Control:
    def __init__(self, ident, name='', kind='Text', password=False, offscreen=False, children=()):
        self.children_ = list(children)
        self.raw = SimpleNamespace(CurrentIsPassword=password, CurrentIsOffscreen=offscreen, GetRuntimeId=lambda:[ident])
        self.element_info = SimpleNamespace(element=self.raw, name=name, control_type=kind, automation_id=str(ident))
        self.iface_value = SimpleNamespace(CurrentValue=name)
    def rectangle(self):
        return SimpleNamespace(left=10, top=20, right=100, bottom=80)
    def children(self):
        return self.children_


def capture(monkeypatch, root, foreground=None):
    monkeypatch.setattr(platform, 'system', lambda:'Windows')
    monkeypatch.setattr(observer, '_foreground_window', foreground or (lambda:(123,'Kingdom Test')))
    import sys
    monkeypatch.setitem(sys.modules,'pywinauto',SimpleNamespace(Desktop=lambda **_:SimpleNamespace(window=lambda **_:SimpleNamespace(wrapper_object=lambda:root))))
    return observer._observe_worker({'window_title':'Kingdom Test'})


def test_observer_redacts_password_and_omits_unknown_or_hidden_text(monkeypatch):
    root=Control(1,'Test',kind='Window',children=[Control(2,'visible'),Control(3,'secret-password',kind='Edit',password=True),Control(4,'unknown-password',password=None),Control(5,'hidden',offscreen=True),Control(6,'typed value',kind='Edit')])
    state=capture(monkeypatch,root)
    encoded=json.dumps(state)
    assert state['ok'] and 'typed value' in encoded and '[REDACTED]' in encoded
    assert all(text not in encoded for text in ('secret-password','unknown-password','hidden'))
    assert type(state['observed_at']) in (int,float) and state['window_handle']==123


def test_total_controls_and_text_are_bounded(monkeypatch):
    state=capture(monkeypatch,Control(1,'root',children=[Control(i,'x'*1000) for i in range(2,300)]))
    assert len(state['controls'])<=100
    assert sum(len(c.get('name',''))+len(c.get('automation_id',''))+len(c.get('text','')) for c in state['controls'])<=15000


def test_foreground_change_discards_captured_content(monkeypatch):
    windows=iter([(123,'Kingdom Test'),(456,'Other Window')])
    result=capture(monkeypatch,Control(1,'private screen text'),lambda:next(windows))
    assert result=={'ok':False,'error':'foreground_changed'}
    assert 'private' not in json.dumps(result)


def test_observer_never_reads_a_parent_document_range(monkeypatch):
    root=Control(1,'Page',kind='Document')
    root.iface_text=SimpleNamespace(DocumentRange=SimpleNamespace(GetText=lambda _:pytest.fail('Parent DocumentRange must not be read')))
    assert capture(monkeypatch,root)['ok']


def test_public_adapter_is_bounded_and_passes_only_the_selected_title(monkeypatch):
    monkeypatch.setattr(platform,'system',lambda:'Windows')
    seen={}
    class Child:
        returncode=0
        def communicate(self,**kwargs):
            seen.update(kwargs)
            return json.dumps({'ok':True,'window_handle':123,'window_title':'Kingdom Test','observed_at':1.0,'controls':[]}).encode(),None
    def launch(argv,**kwargs):
        seen.update(kwargs);seen['argv']=argv
        return Child()
    monkeypatch.setattr(observer.subprocess,'Popen',launch)
    state=observer.desktop_observe({'window_title':'Kingdom Test','_receipt_id':'internal-receipt'})
    assert state['ok'] and seen['timeout']==12 and seen['shell'] is False
    assert json.loads(seen['input'])=={'window_title':'Kingdom Test'}
    assert seen['argv'][-1]=='--worker'


def test_wayland_reports_unsupported_without_launching(monkeypatch):
    monkeypatch.setattr(platform,'system',lambda:'Linux')
    monkeypatch.setenv('WAYLAND_DISPLAY','wayland-0')
    monkeypatch.setattr(observer.subprocess,'Popen',lambda *_a,**_k:pytest.fail('No process should start'))
    assert observer.desktop_observe({'window_title':'Test'})['error']=='foreground_probe_unavailable'


@pytest.mark.parametrize('system,name',[('Linux','_linux_identity'),('Darwin','_mac_identity')])
def test_optional_identity_adapter_never_claims_accessibility_or_input(monkeypatch,system,name):
    from backend.runtime import desktop_platforms
    monkeypatch.setattr(platform,'system',lambda:system)
    monkeypatch.setattr(desktop_platforms,name,lambda:(42,'Test'))
    result=observer.desktop_observe({'window_title':'Test'})
    assert result['ok'] and result['window_handle']==42
    assert result['controls']==[] and not result['input_supported']
    assert result['observation_scope']=='foreground_identity_only'
    assert observer.desktop_observe({'window_title':'Other'})['ok'] is False


def test_optional_identity_discards_focus_change(monkeypatch):
    from backend.runtime import desktop_platforms
    events=iter([(42,'Test'),(43,'Test')])
    monkeypatch.setattr(desktop_platforms,'_linux_identity',lambda:next(events))
    assert desktop_platforms.observe_identity({'window_title':'Test'},'Linux')=={'ok':False,'error':'foreground_changed'}
