"""Real Git reconstruction tests; candidate code is never imported."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import unittest
from tempfile import TemporaryDirectory

spec = importlib.util.spec_from_file_location('preparation', Path(__file__).parents[1] / 'scripts/jules-source-preparation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)



@unittest.skipUnless(shutil.which('git'), 'Real Git executable required')
class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = {**os.environ, 'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                    'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=self.repo, env=self.env)
        git('init', '-q')
        (self.repo / 'example.py').write_text('VALUE = 1\n', encoding='utf-8')
        git('add', '.')
        git('commit', '-qm', 'Fixture base')
        self.revision = git('rev-parse', 'HEAD').decode().strip()
        (self.repo / 'example.py').write_text('VALUE = 2\n', encoding='utf-8')
        self.patch = git('diff', '--no-ext-diff')
        self.sha = hashlib.sha256(self.patch).hexdigest()

    def tearDown(self):
        for path in self.root.rglob('*'):
            path.chmod(0o777)
        self.temp.cleanup()

    def test_reconstructs_exact_git_base_and_retained_patch(self):
        out = self.root / 'review'
        proof = module.prepare(self.repo, self.revision, self.patch, self.sha, out, ['example.py'])
        self.assertEqual((out / 'source/example.py').read_text(), 'VALUE = 2\n')
        self.assertEqual(proof['base_revision'], self.revision)
        self.assertEqual(proof['patch_sha256'], self.sha)
        self.assertEqual(proof['candidate_tree_sha256'], module.tree_digest(out / 'source'))
        self.assertEqual(proof, json.loads((out / 'preparation.json').read_text()))
        self.assertEqual(proof['changed_paths'], ['example.py'])

    def test_changed_provider_bytes_rejected_before_creating_source(self):
        out = self.root / 'review'
        with self.assertRaisesRegex(ValueError, 'digest changed'):
            module.prepare(self.repo, self.revision, self.patch + b'\n', self.sha, out, ['example.py'])
        self.assertFalse(out.exists())

    def test_patch_cannot_expand_operator_scope(self):
        with self.assertRaisesRegex(ValueError, 'file scope'):
            module.prepare(self.repo, self.revision, self.patch, self.sha, self.root / 'review', ['different.py'])

    def test_wrong_base_cannot_apply_a_patch(self):
        with self.assertRaises(ValueError):
            module.prepare(self.repo, 'f' * 40, self.patch, self.sha, self.root / 'review', ['example.py'])

    def test_unsafe_paths_are_rejected(self):
        for name in ['../escape', '/absolute', '.git/config', 'nested/.GiT/hooks/x', 'C:/escape', 'back\\slash']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.safe_path(name)

    def test_existing_review_is_never_overwritten(self):
        out = self.root / 'review'
        out.mkdir()
        sentinel = out / 'receipt'
        sentinel.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'fresh review'):
            module.prepare(self.repo, self.revision, self.patch, self.sha, out, ['example.py'])
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_export_attributes_do_not_remove_or_rewrite_raw_committed_source(self):
        (self.repo/'example.py').write_text('VALUE = 1\n',encoding='utf-8')
        (self.repo/'.gitattributes').write_text('kept.txt export-ignore\nversion.txt export-subst\n',encoding='utf-8')
        (self.repo/'kept.txt').write_text('retain raw bytes\n',encoding='utf-8')
        (self.repo/'version.txt').write_text('$Format:%H$\n',encoding='utf-8')
        (self.repo/'nested').mkdir()
        (self.repo/'nested/value.txt').write_text('nested raw blob\n',encoding='utf-8')
        subprocess.check_call(['git','add','.'],cwd=self.repo,env=self.env)
        subprocess.check_call(['git','commit','-qm','Raw attributes fixture'],cwd=self.repo,env=self.env)
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.repo,env=self.env).decode().strip()
        out=self.root/'review'
        module.prepare(self.repo,revision,self.patch,self.sha,out,['example.py'])
        self.assertEqual((out/'source/kept.txt').read_text(),'retain raw bytes\n')
        self.assertEqual((out/'source/version.txt').read_text(),'$Format:%H$\n')
        self.assertEqual((out/'source/nested/value.txt').read_text(),'nested raw blob\n')

if __name__ == '__main__':
    unittest.main()
