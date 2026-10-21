"""Version preparation is local, review-gated and preserves source/dependencies."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import prepare_version as preparation
from scripts.validate_version import (PACKAGES, LOCKS, REVIEW_MARKER, get_authoritative_version,
                                      metadata_errors, release_identity, validate_tag)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def release_tree(tmp_path):
    def write(relative, text):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    write('backend/state.py', '# keep this comment\nSTATE = {"running": False, "version": "1.2.2"}\n')
    for relative in PACKAGES:
        write(relative, json.dumps({'name': 'fixture', 'version': '1.2.2', 'dependencies': {'keep': '1.2.2'}}))
    for relative in LOCKS:
        write(relative, json.dumps({'version': '1.2.2', 'packages': {'': {'version': '1.2.2'},
                                                                'node_modules/keep': {'version': '1.2.2'}}}))
    write('apps/mobile/native/android/app/build.gradle', 'versionCode 1010201\nversionName "1.1.2"\n')
    write('apps/mobile/native/ios/App/App.xcodeproj/project.pbxproj', 'CURRENT_PROJECT_VERSION = 1;\nMARKETING_VERSION = 1.0;\n')
    write('docs/releases/v1.2.2.md', '# Reviewed existing release\nActual limits are recorded here.\n')
    return tmp_path


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_dry_run_cli_performs_zero_writes_and_reports_full_plan(release_tree):
    before = snapshot(release_tree)
    result = subprocess.run([sys.executable, str(REPO / 'scripts/prepare_version.py'), '1.2.3',
                             '--root', str(release_tree)], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report['apply'] is False and len(report['files']) == 11
    assert snapshot(release_tree) == before


@pytest.mark.parametrize('version', ['1.2.3', '2.0.0'])
def test_apply_synchronizes_future_versions_without_mutating_dependencies_or_store_builds(release_tree, version):
    plan = preparation.prepare(release_tree, version)
    preparation.apply(release_tree, plan)
    assert get_authoritative_version(str(release_tree)) == version
    assert not metadata_errors(release_tree, version)
    for relative in PACKAGES:
        assert json.loads((release_tree / relative).read_text())['dependencies']['keep'] == '1.2.2'
    for relative in LOCKS:
        assert json.loads((release_tree / relative).read_text())['packages']['node_modules/keep']['version'] == '1.2.2'
    android = (release_tree / 'apps/mobile/native/android/app/build.gradle').read_text()
    ios = (release_tree / 'apps/mobile/native/ios/App/App.xcodeproj/project.pbxproj').read_text()
    assert f'versionName "{version}"' in android and 'versionCode 1010201' in android
    assert f'MARKETING_VERSION = {version};' in ios and 'CURRENT_PROJECT_VERSION = 1;' in ios
    with pytest.raises(ValueError, match='review'):
        release_identity(release_tree)
    notes = release_tree / f'docs/releases/v{version}.md'
    notes.write_text('# Reviewed release\nBounded changes; actual results only.\n')
    assert release_identity(release_tree) == {'version': version, 'tag': f'v{version}', 'notes': f'docs/releases/v{version}.md'}


@pytest.mark.parametrize('version', ['1.2.2', '1.1.9', '01.3.0', '1.2.3-rc.1', '1.2.3\n', '1.2.3/../../oops'])
def test_invalid_or_non_increasing_version_never_changes_files(release_tree, version):
    before = snapshot(release_tree)
    with pytest.raises(ValueError):
        preparation.prepare(release_tree, version)
    assert snapshot(release_tree) == before


def test_explicit_migration_for_old_native_package_metadata(release_tree):
    target = release_tree / 'apps/mobile/native/package.json'
    data = json.loads(target.read_text()); data['version'] = '1.1.2'; target.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='repair-existing-metadata'):
        preparation.prepare(release_tree, '1.2.3')
    plan = preparation.prepare(release_tree, '1.2.3', repair_existing=True)
    assert plan['existing_metadata_errors']
    preparation.apply(release_tree, plan)
    assert not metadata_errors(release_tree, '1.2.3')


def test_changed_source_and_existing_notes_fail_without_overwrite(release_tree):
    plan = preparation.prepare(release_tree, '1.2.3')
    source = release_tree / 'backend/state.py'
    source.write_text(source.read_text() + '# concurrent edit\n')
    before = snapshot(release_tree)
    with pytest.raises(ValueError, match='changed'):
        preparation.apply(release_tree, plan)
    assert snapshot(release_tree) == before
    (release_tree / 'docs/releases/v1.2.3.md').write_text('Owner notes')
    with pytest.raises(ValueError, match='already exist'):
        preparation.prepare(release_tree, '1.2.3')


def test_mid_write_failure_rolls_back_all_metadata(release_tree, monkeypatch):
    plan = preparation.prepare(release_tree, '1.2.3')
    before = snapshot(release_tree)
    original = preparation.os.replace
    calls = 0
    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError('injected write failure')
        return original(source, target)
    monkeypatch.setattr(preparation.os, 'replace', fail_once)
    with pytest.raises(OSError):
        preparation.apply(release_tree, plan)
    assert snapshot(release_tree) == before


def test_lock_prevents_overlapping_preparation(release_tree):
    plan = preparation.prepare(release_tree, '1.2.3')
    (release_tree / '.version-preparation.lock').write_text('retained interrupted preparation')
    before = snapshot(release_tree)
    with pytest.raises(FileExistsError):
        preparation.apply(release_tree, plan)
    assert snapshot(release_tree) == before


def test_failed_rollback_retains_inspection_lock(release_tree, monkeypatch):
    plan = preparation.prepare(release_tree, '1.2.3')
    original = preparation.os.replace
    calls = 0
    def fail_after_first(source, target):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError('write and rollback unavailable')
        return original(source, target)
    monkeypatch.setattr(preparation.os, 'replace', fail_after_first)
    with pytest.raises(OSError):
        preparation.apply(release_tree, plan)
    assert (release_tree / '.version-preparation.lock').is_file()
    with pytest.raises(FileExistsError):
        preparation.apply(release_tree, plan)


def test_identity_rejects_malformed_authority_unreviewed_notes_and_wrong_tag(release_tree, monkeypatch):
    assert validate_tag('v1.2.2', '1.2.2') and not validate_tag('vv1.2.2', '1.2.2')
    notes = release_tree / 'docs/releases/v1.2.2.md'
    notes.write_text(REVIEW_MARKER)
    with pytest.raises(ValueError):
        release_identity(release_tree)
    notes.write_text('Reviewed notes')
    monkeypatch.setenv('GITHUB_REF', 'refs/tags/v9.9.9')
    result = subprocess.run([sys.executable, str(REPO / 'scripts/validate_version.py'), '--root', str(release_tree),
                             '--release-identity'], capture_output=True, text=True)
    assert result.returncode and 'Triggered tag' in result.stderr
    (release_tree / 'backend/state.py').write_text('STATE = dict(version="1.2.2")\n')
    with pytest.raises(ValueError):
        get_authoritative_version(str(release_tree))


def test_workflow_uses_setup_identity_and_retains_failclosed_publish_gates():
    import yaml
    workflow = yaml.safe_load((REPO / '.github/workflows/release.yml').read_text())
    jobs = workflow['jobs']
    assert jobs['native-build']['needs'] == 'identity'
    assert set(jobs['publish']['needs']) == {'identity', 'native-build'}
    assert jobs['publish']['env']['RELEASE_TAG'] == '${{ needs.identity.outputs.tag }}'
    script = '\n'.join(step.get('run', '') for step in jobs['publish']['steps'])
    assert 'v1.2.2' not in script
    assert 'ref="refs/tags/$RELEASE_TAG"' in script
    assert 'refusing to replace stable assets' in script
    assert 'Existing tag targets different source' in script
    assert script.count('grep -Fx "$RELEASE_COMMIT"') >= 3
    assert 'diff -u release_staging/SHA256SUMS release_download/SHA256SUMS' in script
    assert 'sha256sum -c SHA256SUMS' in script
    assert '--draft=false --prerelease=false --latest' in script
