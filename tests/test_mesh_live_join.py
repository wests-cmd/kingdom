"""Three real backends: one approval, reciprocal links, restart and revocation."""
import json
import datetime
import ipaddress
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def test_three_backend_automatic_mesh(tmp_path):
    source = str(Path(__file__).parents[1])
    token = secrets.token_urlsafe(48)
    nodes = []
    certificates = []

    def invoke(node, path, body=None, method=None):
        req = urllib.request.Request(node['url'] + path, method=method or ('POST' if body is not None else 'GET'),
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'X-Kingdom-Request': '1'})
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)

    def wait_for(check, timeout=65):
        until = time.monotonic() + timeout
        last = None
        while time.monotonic() < until:
            try:
                last = check()
                if last: return last
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(.3)
        raise AssertionError('Mesh condition did not converge: ' + str(last))

    def start(node):
        env = {**os.environ, 'PYTHONPATH': source, 'KINGDOM_OWNER_TOKEN': token}
        # Each process owns independent persistent state and real signing keys.
        node['log'] = (node['dir'] / 'server.log').open('a')
        node['process'] = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
            '--host', '127.0.0.1', '--port', str(node['port']), '--no-access-log'], cwd=node['dir'], env=env,
            stdout=node['log'], stderr=subprocess.STDOUT)
        wait_for(lambda: invoke(node, '/nodes/identity'))
        node['identity'] = invoke(node, '/nodes/identity')

    def stop(node):
        process = node.get('process')
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        if node.get('log'): node['log'].close()

    def listen(node):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node['identity']['node_id'])])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
        pem = cert.public_bytes(serialization.Encoding.PEM).decode()
        certificates.append(pem)
        certfile, keyfile = node['dir'] / 'tls.crt', node['dir'] / 'tls.key'
        certfile.write_text(pem)
        keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        config = node['dir'] / 'listener.json'
        config.write_text(json.dumps({'mode':'server', 'mesh_enabled':True, 'peers':[], 'local':node['url'],
            'identity':node['identity'], 'bind':'127.0.0.1', 'port':port, 'cert_file':str(certfile), 'key_file':str(keyfile)}))
        node['peer_url'] = f'https://127.0.0.1:{port}'
        node['listener_log'] = (node['dir'] / 'listener.log').open('w')
        node['listener'] = subprocess.Popen([sys.executable, source + '/scripts/peer-heartbeat-link.py', '--config', str(config)],
            stdout=node['listener_log'], stderr=subprocess.STDOUT)
        import ssl
        context = ssl.create_default_context(cadata=pem)
        wait_for(lambda: json.load(urllib.request.urlopen(node['peer_url'] + '/nodes/identity', context=context, timeout=3)))

    def peers(node):
        result = invoke(node, '/nodes')
        rows = result.get('nodes', []) if isinstance(result, dict) else result
        return {row.get('node_id', row.get('id')): row for row in rows}

    def connected():
        for node in nodes:
            rows = peers(node)
            for other in nodes:
                if other is node: continue
                if rows.get(other['identity']['node_id'], {}).get('node_state') != 'CONNECTED': return False
        return True

    try:
        for index in range(3):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            folder = tmp_path / str(index); folder.mkdir()
            node = {'port': port, 'url': f'http://127.0.0.1:{port}', 'dir': folder}
            nodes.append(node); start(node)
            listen(node)
        ca_bundle = ''.join(certificates)
        import ssl
        context = ssl.create_default_context(cadata=ca_bundle)
        for node in nodes:
            with urllib.request.urlopen(node['peer_url'] + '/nodes/identity', context=context, timeout=5) as response:
                assert json.load(response) == node['identity']
        authority = nodes[0]
        invoke(authority, '/federation/mesh', {'authority_id': authority['identity']['node_id'],
                                             'local_endpoint': authority['peer_url'], 'ca_pem':ca_bundle}, method='PUT')
        for node in nodes[1:]:
            invitation = invoke(authority, '/nodes/invitation', {})
            pin = invoke(node, '/federation/mesh/destinations', {
                'authority_endpoint': authority['peer_url'], 'invitation': invitation})
            result = invoke(node, '/federation/mesh/join', {'invitation': invitation,
                'destination_approval_id': pin['approval_id'],
                'authority_endpoint': authority['peer_url'], 'local_endpoint': node['peer_url'], 'ca_pem':ca_bundle})
            assert result['status'] == 'pending_owner_approval'
            invoke(authority, '/nodes/' + node['identity']['node_id'] + '/approve', {'granted_capabilities': []})
        # No per-pair setup or manual sync/reconnect calls.
        wait_for(connected)
        for node in nodes:
            for other in nodes:
                if other is not node:
                    assert peers(node)[other['identity']['node_id']]['granted_capabilities'] == []
        newcomer = nodes[2]
        old_identity = newcomer['identity']
        stop(newcomer); start(newcomer)
        assert newcomer['identity'] == old_identity
        wait_for(connected)
        invoke(authority, '/nodes/' + newcomer['identity']['node_id'] + '/revoke', {})
        wait_for(lambda: peers(nodes[1]).get(newcomer['identity']['node_id'], {}).get('node_state') == 'REVOKED')
        # Native signed RPC must reject the removed member on another Knight.
        proof = invoke(newcomer, '/federation/' + nodes[1]['identity']['node_id'] + '/heartbeat-proof', {})
        try:
            invoke(nodes[1], '/nodes/rpc', proof)
            raise AssertionError('Revoked Knight was accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 403
        (tmp_path / 'mesh-receipt.json').write_text(json.dumps({'result': 'passed', 'nodes': [n['identity']['node_id'] for n in nodes],
            'automatic_pairs': 3, 'directions': 6, 'restart': True, 'revocation': True, 'new_grants': 0,
            'transport':'HTTPS through real restricted peer listeners'}), encoding='utf-8')
    except Exception:
        diagnostics = []
        for node in nodes:
            try: diagnostics.append({'port':node['port'], 'links':invoke(node,'/federation/connections/status'), 'membership':invoke(node,'/federation/mesh')})
            except OSError: pass
        (tmp_path / 'failure-status.json').write_text(json.dumps(diagnostics), encoding='utf-8')
        raise
    finally:
        for node in nodes:
            stop(node)
            listener = node.get('listener')
            if listener:
                listener.terminate()
                try: listener.wait(timeout=5)
                except subprocess.TimeoutExpired: listener.kill(); listener.wait(timeout=5)
            if node.get('listener_log'): node['listener_log'].close()
