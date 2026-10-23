from types import SimpleNamespace
from backend.runtime import service_discovery
from backend.cluster.apprentice_inventory import validate_inventory


def test_service_discovery_reports_observation_not_permission(monkeypatch):
    monkeypatch.setattr(service_discovery.platform,'system',lambda:'Linux')
    monkeypatch.setattr(service_discovery,'in_container',lambda:False)
    monkeypatch.setattr(service_discovery.shutil,'which',lambda name:'/usr/bin/systemctl')
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0,stdout='[{"unit":"example.service","description":"Example app"}]')
    monkeypatch.setattr(service_discovery.subprocess,'run',run)
    report=service_discovery.discover_local_services()
    assert report['state']=='observed' and report['services'][0]['id']=='example.service'
    assert 'list-units' in calls[0] and '--user' in calls[0]
    assert not any(word in calls[0] for word in ('start','stop','restart'))
    assert validate_inventory({'version':1,'apprentices':[],'services':report})['services']['state']=='observed'


def test_service_failure_is_unknown_not_an_empty_success(monkeypatch):
    monkeypatch.setattr(service_discovery.platform,'system',lambda:'Linux')
    monkeypatch.setattr(service_discovery,'in_container',lambda:False)
    monkeypatch.setattr(service_discovery.shutil,'which',lambda name:'/usr/bin/systemctl')
    monkeypatch.setattr(service_discovery.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=''))
    assert service_discovery.discover_local_services()['state']=='unavailable'
