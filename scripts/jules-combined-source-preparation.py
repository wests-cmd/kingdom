"""Prepare one ordered returned-patch composition; never execute candidate code.

The CLI requires protected operator inputs and existing cryptography support.
Preparation is not a combined functional/integration verdict or authorization.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import time

CONTEXT = b'kingdom.independent-patch-test.v2\0'
BINDING = {'job_id','project','backlog_id','mission_id','mission_version','step_id',
           'source','base_revision','patch_sha256','contract_sha256'}
REGISTRY = Path('/etc/kingdom/independent-reviewers.json')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:raise ValueError('Duplicate operator or receipt field')
        result[key] = value
    return result


def read_json(path, limit):
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > limit:
        raise ValueError('Bounded ordinary operator/receipt file required')
    with path.open('rb') as handle:data = handle.read(limit+1)
    if len(data) > limit:raise ValueError('Operator/receipt byte budget exceeded')
    return json.loads(data,object_pairs_hook=unique_object)


def sibling(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def protected(path, private=False):
    path = Path(path).absolute()
    if os.name != 'posix' or path.resolve() != path:
        raise ValueError('Protected POSIX paths without symlinks required')
    for entry in [path, *path.parents]:
        value = entry.stat()
        if value.st_uid != 0 or value.st_mode & 0o022:
            raise ValueError('Root-owned non-writable operator inputs required')
    if private and path.stat().st_mode & 0o077:
        raise ValueError('Private operator configuration required')
    return path


def verify_receipt(envelope, expected, reviewers, now):
    """Cryptographically validate an exact, current passing component verdict."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not isinstance(envelope, dict) or set(envelope) != {'payload','signature'}:
            raise ValueError('Exact signed envelope required')
        proof = envelope['payload']
        if (not isinstance(proof, dict) or set(proof) != {'format','receipt_id','reviewer_id','issued_at','expires_at','binding','execution'}
                or proof['format'] != 'kingdom.patch-test.v2' or set(proof['binding']) != BINDING
                or set(expected) != {'receipt_id','receipt_sha256','binding'}
                or canonical(proof['binding']) != canonical(expected['binding'])
                or proof['receipt_id'] != expected['receipt_id']
                or sha(canonical(envelope)) != expected['receipt_sha256']):
            raise ValueError('Receipt identity, hash, order or binding changed')
        for key in ('receipt_id','reviewer_id'):
            if not isinstance(proof[key], str) or not re.fullmatch('[A-Za-z0-9_.-]{1,120}', proof[key]):
                raise ValueError('Bounded receipt/reviewer identity required')
        issued, expiry = proof['issued_at'], proof['expires_at']
        if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (issued,expiry))
                or issued > now + 5 or not issued < expiry or expiry <= now or expiry-issued > 3600):
            raise ValueError('Component receipt expired or outside its original window')
        binding = proof['binding']
        if (type(binding['mission_version']) is not int or binding['mission_version'] < 1
                or any(not isinstance(binding[k], str) or not re.fullmatch('[A-Za-z0-9_.-]{1,120}', binding[k])
                       for k in ('job_id','backlog_id','mission_id','step_id'))
                or not re.fullmatch('[a-f0-9]{40}', binding['base_revision'])
                or any(not re.fullmatch('[a-f0-9]{64}', binding[k]) for k in ('patch_sha256','contract_sha256'))):
            raise ValueError('Exact revision and digest bindings required')
        reviewer = reviewers[proof['reviewer_id']]
        if any(not isinstance(reviewer.get(k),list) or len(reviewer[k]) > 100
               or any(not isinstance(v,str) or len(v)>200 for v in reviewer[k]) for k in ('projects','sources','contracts')):
            raise ValueError('Exact current reviewer scope lists required')
        if (reviewer.get('enabled') is not True or binding['project'] not in reviewer.get('projects', [])
                or binding['source'] not in reviewer.get('sources', [])
                or binding['contract_sha256'] not in reviewer.get('contracts', [])):
            raise ValueError('Component reviewer authority is revoked or out of scope')
        execution = proof['execution']
        fields = {'run_id','image_sha256','source_archive_sha256','candidate_tree_sha256','argv',
                  'test_count','failed_count','exit_code','network_isolated','read_only_source','verdict_origin'}
        if not isinstance(execution,dict) or set(execution) not in (fields,fields|{'diagnostics'}):
            raise ValueError('Exact V2 execution evidence fields required')
        diagnostics = execution.get('diagnostics',[])
        if not isinstance(diagnostics,list) or len(diagnostics)>32:
            raise ValueError('Bounded typed component diagnostics required')
        for diagnostic in diagnostics:
            if (not isinstance(diagnostic,dict) or set(diagnostic)!={'test_id','error_code','status_code'}
                    or not isinstance(diagnostic['test_id'],str) or not re.fullmatch('[A-Za-z0-9_.-]{1,100}',diagnostic['test_id'])
                    or diagnostic['error_code'] not in {'assertion_failed','transport_failed','startup_failed'}
                    or diagnostic['status_code'] is not None and
                       (type(diagnostic['status_code']) is not int or not 100<=diagnostic['status_code']<=599)):
                raise ValueError('Invalid typed component diagnostic')
        if (type(execution.get('test_count')) is not int or execution['test_count'] < 1
                or type(execution.get('failed_count')) is not int or execution['failed_count'] != 0
                or type(execution.get('exit_code')) is not int or execution['exit_code'] != 0
                or execution.get('network_isolated') is not True or execution.get('read_only_source') is not True
                or execution.get('verdict_origin') != 'external_controller'
                or any(not isinstance(execution.get(k), str) or not re.fullmatch('[a-f0-9]{64}', execution[k])
                       for k in ('image_sha256','source_archive_sha256','candidate_tree_sha256'))
                or not isinstance(execution.get('argv'), list) or not 1 <= len(execution['argv']) <= 100
                or any(not isinstance(v,str) or not 1 <= len(v) <= 1000 for v in execution['argv'])
                or not isinstance(execution.get('run_id'), str) or not 1 <= len(execution['run_id']) <= 120):
            raise ValueError('Current nonempty isolated passing component evidence required')
        key = base64.b64decode(reviewer['public_key'], validate=True)
        signature = base64.b64decode(envelope['signature'], validate=True)
        Ed25519PublicKey.from_public_bytes(key).verify(signature, CONTEXT + canonical(proof))
        return proof
    except Exception as error:
        raise ValueError('No current independently signed exact component receipt') from error


def prepare(repository, project, source, revision, expected_inputs, candidates, output, allowed_paths, reviewers, *, now=None):
    """All arguments are operator inputs, not candidate-controlled policy.

    expected_inputs pins the COMPLETE order, identities and canonical envelope
    hashes separately from candidates. Every signature is checked, including for
    direct Python callers. No boolean 'verified' shortcut or verifier callback.
    """
    now = time.time() if now is None else now
    if (project not in {'kingdom','threadmap','centipede'} or not isinstance(source,str)
            or not re.fullmatch(r'sources/github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source)
            or not isinstance(revision,str) or not re.fullmatch('[a-f0-9]{40}', revision)
            or not isinstance(expected_inputs,list) or not 2 <= len(expected_inputs) <= 8
            or not isinstance(candidates,list) or len(candidates) != len(expected_inputs)
            or len(canonical(expected_inputs)) > 65536):
        raise ValueError('Bounded exact operator order, project, source and base required')
    prep = sibling('jules-source-preparation')
    if not isinstance(allowed_paths,list) or not 1 <= len(allowed_paths) <= 100:
        raise ValueError('Exact operator file list required')
    allowed = {str(prep.safe_path(value)) for value in allowed_paths}
    if not allowed or len(allowed) > 100:
        raise ValueError('Bounded exact operator file scope required')
    receipts, total, identities = [], 0, set()
    jobs, patches, components = set(), set(), set()
    for expected, item in zip(expected_inputs, candidates):
        if not isinstance(item,dict) or set(item) != {'patch','attestation'}:
            raise ValueError('Only retained patch bytes and signed attestation are accepted')
        patch = item['patch']
        if not isinstance(patch,bytes) or not 0 < len(patch) <= 2_000_000 or len(canonical(item['attestation'])) > 65536:
            raise ValueError('Bounded retained candidate inputs required')
        total += len(patch)
        if total > 8_000_000:
            raise ValueError('Combined patch byte budget exceeded')
        proof = verify_receipt(item['attestation'], expected, reviewers, now)
        binding = proof['binding']
        if (binding['project'] != project or binding['source'] != source or binding['base_revision'] != revision
                or binding['patch_sha256'] != sha(patch)):
            raise ValueError('Component source, exact base or retained patch hash differs')
        if (proof['receipt_id'] in identities or binding['job_id'] in jobs or sha(patch) in patches
                or binding['backlog_id'] in components):
            raise ValueError('Duplicate receipt, job or patch cannot be composed twice')
        identities.add(proof['receipt_id']); jobs.add(binding['job_id']); patches.add(sha(patch)); components.add(binding['backlog_id'])
        if re.search(rb'\b(?:120000|160000)\b|GIT binary patch|^rename |^copy ', patch, re.M):
            raise ValueError('Links, submodules, copies, renames and binary patches are forbidden')
        receipts.append(proof)
    destination = Path(output)
    if destination.resolve().is_relative_to(Path(repository).resolve()):
        raise ValueError('Keep prepared output outside the immutable source repository')
    first = prep.prepare(repository, revision, candidates[0]['patch'], sha(candidates[0]['patch']), destination, sorted(allowed))
    tree = destination/'source'
    (destination/'preparation.json').rename(destination/'component-1-preparation.json')
    (destination/'candidate.patch').rename(destination/'patch-1.patch')
    if first['candidate_tree_sha256'] != receipts[0]['execution']['candidate_tree_sha256']:
        raise ValueError('First component receipt differs from reconstructed candidate tree')
    if any(r['execution']['source_archive_sha256'] != first['source_archive_sha256'] for r in receipts):
        raise ValueError('Component receipt does not attest the exact raw base archive')
    with tarfile.open(destination/'base.tar.gz') as archive:
        base_bytes = sum(member.size for member in archive if member.isfile())
    retained_size = base_bytes + total + (destination/'base.tar.gz').stat().st_size
    if retained_size * len(candidates) + total + 1_048_576 > 512*1024*1024:
        raise ValueError('Retained independent source verification exceeds the combined disk budget')
    # Validate every individual receipt against base+that patch, NOT against the
    # aggregate after earlier patches. Keep these source/proof records distinct.
    for index, (item, receipt) in enumerate(zip(candidates[1:], receipts[1:]), 2):
        component = prep.prepare(repository, revision, item['patch'], sha(item['patch']),
            destination/f'component-{index}-verification', sorted(allowed))
        if (component['candidate_tree_sha256'] != receipt['execution']['candidate_tree_sha256']
                or component['source_archive_sha256'] != receipt['execution']['source_archive_sha256']):
            raise ValueError('Component receipt differs from independently reconstructed source')
    for path in [tree,*tree.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    env = {key:value for key,value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',
               GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1')

    def git(args, patch):
        result = subprocess.run(['git','-c','protocol.allow=never','-c','core.hooksPath='+os.devnull,*args],
            cwd=tree,input=patch,capture_output=True,env=env,timeout=30)
        if result.returncode:
            raise ValueError('Ordered patch conflict or invalid combined source; no combined proof produced')
        return result.stdout

    ordered, changed = [], set(first['changed_paths'])
    for index, (item, proof, expected) in enumerate(zip(candidates,receipts,expected_inputs), 1):
        if index > 1:
            stats = git(['apply','--numstat','-z','-'],item['patch'])
            names = []
            for record in stats.split(b'\0'):
                if not record:continue
                fields = record.split(b'\t')
                if len(fields) != 3 or not all(v.isdigit() for v in fields[:2]):
                    raise ValueError('Only ordinary textual file patches are supported')
                names.append(str(prep.safe_path(fields[2].decode('utf-8'))))
            if not names or any(name not in allowed for name in names):
                raise ValueError('Combined patch exceeds the operator file scope')
            git(['apply','--check','-'],item['patch'])
            git(['apply','--whitespace=nowarn','-'],item['patch'])
            changed.update(names)
            (destination/f'patch-{index}.patch').write_bytes(item['patch'])
        (destination/f'receipt-{index}.json').write_bytes(canonical(item['attestation']))
        ordered.append({**expected,'index':index,'reviewer_id':proof['reviewer_id'],
                        'tree_after_patch_sha256':prep.tree_digest(tree)})
    for path in [tree,*tree.rglob('*')]:
        path.chmod(0o555 if path.is_dir() else 0o444)
    result = dict(format='kingdom.combined-source-preparation.v1', project=project, source=source,
        base_revision=revision, source_archive_sha256=first['source_archive_sha256'],
        ordered_inputs=ordered, ordered_inputs_sha256=sha(canonical(expected_inputs)),
        combined_tree_sha256=prep.tree_digest(tree), changed_paths=sorted(changed),
        scope='Source preparation only; no combined tests, execution, acceptance or publication authorized')
    result['provenance_sha256'] = sha(canonical(result))
    (destination/'combined-preparation.json').write_bytes(canonical(result))
    return result


def run(config_path):
    if not sys.flags.isolated:
        raise ValueError('Launch the protected preparer with Python -I')
    for name in ('jules-combined-source-preparation','jules-source-preparation','archive-verified-source'):
        protected(Path(__file__).with_name(name+'.py'))
    crypto = importlib.util.find_spec('cryptography')
    if crypto is None or not crypto.origin:
        raise ValueError('Existing operator-protected cryptography installation required; no automatic installation')
    package = protected(crypto.origin).parent
    for path in package.rglob('*'):protected(path)
    config_path = protected(config_path,private=True)
    if not stat.S_ISREG(config_path.stat().st_mode) or config_path.stat().st_size > 65536:raise ValueError('Bounded private operator plan required')
    config = read_json(config_path,65536)
    if set(config) != {'repository','project','source','base_revision','expected_inputs','candidates','output','allowed_paths'}:
        raise ValueError('Exact operator composition configuration required')
    repo = protected(config['repository'])
    if not (repo/'HEAD').is_file() or not (repo/'objects').is_dir():
        raise ValueError('Protected immutable bare mirror required')
    for path in repo.rglob('*'):protected(path)
    output = Path(config['output']).absolute()
    protected(output.parent,private=True)
    registry = protected(REGISTRY)
    if not stat.S_ISREG(registry.stat().st_mode) or registry.stat().st_size > 65536:raise ValueError('Bounded fixed reviewer registry required')
    trust = read_json(registry,65536)
    if type(trust.get('version')) is not int or trust['version'] != 1 or not isinstance(trust.get('reviewers'),dict):
        raise ValueError('Fixed current reviewer trust required')
    candidates=[]
    if not isinstance(config['candidates'],list) or not 2 <= len(config['candidates']) <= 8:
        raise ValueError('Bounded ordered retained input list required')
    for item in config['candidates']:
        if not isinstance(item,dict) or set(item) != {'patch_file','receipt_file'}:
            raise ValueError('Operator-retained input file paths required')
        patch, receipt = protected(item['patch_file']), protected(item['receipt_file'])
        if (not stat.S_ISREG(patch.stat().st_mode) or not stat.S_ISREG(receipt.stat().st_mode)
                or patch.stat().st_size > 2_000_000 or receipt.stat().st_size > 65536):
            raise ValueError('Retained input exceeds its budget')
        with patch.open('rb') as handle:patch_bytes=handle.read(2_000_001)
        candidates.append({'patch':patch_bytes,'attestation':read_json(receipt,65536)})
    return prepare(repo, config['project'], config['source'], config['base_revision'], config['expected_inputs'],
                   candidates, output, config['allowed_paths'], trust['reviewers'])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    args=parser.parse_args();print(json.dumps(run(args.config),sort_keys=True))
