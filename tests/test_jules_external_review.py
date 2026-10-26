"""Supervisor control-plane tests; mocked Docker is never production evidence."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('external_review',Path(__file__).parents[1]/'scripts/jules-external-review.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExternalReviewTests(unittest.TestCase):
    def test_cleanup_resolves_unique_name_to_matching_owned_id(self):
        ident='a'*64
        inspected=[{'Id':ident,'Config':{'Labels':{'kingdom.external-review-run':'external-fixture'}}}]
        with patch.object(module.subprocess,'run',side_effect=[
                SimpleNamespace(returncode=0,stdout=json.dumps(inspected)),
                SimpleNamespace(returncode=0,stdout='')]) as run:
            self.assertTrue(module.cleanup_candidate('kingdom-review-fixture','external-fixture'))
            self.assertEqual(run.call_args.args[0],['docker','rm','--force',ident])

    def test_cleanup_never_removes_another_run(self):
        inspected=[{'Id':'a'*64,'Config':{'Labels':{'kingdom.external-review-run':'other'}}}]
        with patch.object(module.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(inspected))) as run:
            with self.assertRaises(ValueError):module.cleanup_candidate('fixture','external-fixture')
            self.assertEqual(run.call_count,1)

    def test_unknown_startup_requires_positive_absence_or_cleanup(self):
        with patch.object(module.subprocess,'run',side_effect=[
                SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=1,stdout='')]):
            self.assertFalse(module.cleanup_candidate('fixture','external-fixture'))
        with patch.object(module.subprocess,'run',side_effect=[
                SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=0,stdout='')]):
            self.assertTrue(module.cleanup_candidate('fixture','external-fixture'))

    @unittest.skipUnless(os.name=='posix','POSIX durability primitive')
    def test_intent_is_atomically_written_private_and_parseable(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'intent.json'
            module.durable_json(path,{'run_id':'external-fixture'})
            self.assertEqual(json.loads(path.read_text()),{'run_id':'external-fixture'})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertFalse(path.with_name(path.name+'.tmp').exists())

    def test_stale_candidate_blocks_new_work_until_cleanup_reconciles(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);run=root/('external-'+'a'*32);run.mkdir()
            (run/'container-intent.json').write_text(json.dumps(dict(name='kingdom-review-'+'b'*16,run_id=run.name)))
            with patch.object(module,'protected'),patch.object(module,'cleanup_candidate',return_value=False):
                with self.assertRaisesRegex(ValueError,'no new candidate'):module.recover_candidates(root)
            self.assertFalse((run/'cleanup-complete').exists())
            with patch.object(module,'protected'),patch.object(module,'cleanup_candidate',return_value=True):
                module.recover_candidates(root)
            self.assertTrue((run/'cleanup-complete').exists())

    def test_contract_hash_binds_the_raw_source_exporter(self):
        original=module.contract_digest()
        read=Path.read_bytes
        def changed(path):
            value=read(path)
            return value+b'\n# changed raw source exporter\n' if path.name=='archive-verified-source.py' else value
        with patch.object(Path,'read_bytes',changed):self.assertNotEqual(original,module.contract_digest())

    def test_diagnostic_timeout_or_write_failure_never_skips_cleanup(self):
        for failure in ('timeout','write'):
            with self.subTest(failure=failure),TemporaryDirectory() as directory:
                root=Path(directory)
                if failure=='write':(root/'candidate-startup.log').mkdir()
                with patch.object(module,'bounded_logs',side_effect=TimeoutError('fixture')) as logs,\
                        patch.object(module,'cleanup_candidate',return_value=True) as cleanup:
                    module.finish_candidate(root,'a'*64,'fixture','run-fixture')
                    cleanup.assert_called_once_with('fixture','run-fixture')
                    self.assertTrue((root/'cleanup-complete').exists())

    @unittest.skipUnless(os.name=='posix','POSIX pipe selector')
    def test_diagnostic_stream_has_a_hard_byte_limit(self):
        popen=subprocess.Popen
        children=[]
        def child(*args,**kwargs):
            process=popen([sys.executable,'-c',"import sys,time;sys.stdout.buffer.write(b'x'*1000000);sys.stdout.flush();time.sleep(30)"],**kwargs)
            children.append(process)
            return process
        with patch.object(module.subprocess,'Popen',side_effect=child):
            self.assertEqual(len(module.bounded_logs('fixture',limit=1024)),1024)
        self.assertIsNotNone(children[0].poll())

    @unittest.skipUnless(os.name=='posix','POSIX durable launch intent')
    def test_preparation_cannot_launch_after_the_review_deadline(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);mirror=root/'mirror';mirror.mkdir();(mirror/'objects').mkdir();(mirror/'HEAD').write_text('fixture')
            key=root/'key';key.write_bytes(b'x'*32);candidate=root/'candidate.patch';candidate.write_bytes(b'fixture')
            config=dict(binding=dict(job_id='fixture',project='kingdom',backlog_id='fixture',mission_id='fixture',mission_version=1,
                step_id='review',source='sources/github/wests-cmd/kingdom',base_revision='a'*40,patch_sha256='b'*64,
                contract_sha256=module.contract_digest()),reviewer_id='fixture',signing_key=str(key),
                repository_directory=str(mirror),patch_file=str(candidate),deadline_at=300,image='sha256:'+'c'*64,allowed_paths=['fixture.py'])
            path=root/'config.json';path.write_text(json.dumps(config))
            def prepare(repository,revision,raw,sha,run,allowed):
                run.mkdir();(run/'source').mkdir()
                return dict(candidate_tree_sha256='d'*64,source_archive_sha256='e'*64)
            with patch.object(module,'protected',side_effect=lambda path,**kwargs:Path(path)),\
                    patch.object(module,'load',return_value=SimpleNamespace(prepare=prepare)),\
                    patch.object(module.time,'time',side_effect=[0,0,301]),\
                    patch.object(module.subprocess,'run') as command:
                with self.assertRaisesRegex(ValueError,'no candidate launched'):module._execute(path)
                command.assert_not_called()


if __name__=='__main__':unittest.main()
