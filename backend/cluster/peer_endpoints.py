from urllib.parse import urlsplit


def endpoint(value):
    p = urlsplit(value)
    if p.scheme not in {'https', 'http'} or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in {'', '/'}:
        raise ValueError('Use the other Kingdom base URL without credentials or a path')
    if p.scheme == 'http' and p.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Remote Kingdoms require HTTPS')
    return value.rstrip('/')
