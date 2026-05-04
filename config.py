import yaml

def load():
    try:
        return yaml.safe_load(open("kingdom_config.yaml"))
    except:
        return {}
