import base64
from copy import deepcopy
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from backend.runtime.patch_acceptance import canonical,verify_attestation


class PatchAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.binding=dict(job_id='job',project='kingdom',backlog_id='work',mission_id='mission',mission_version=1,step_id='tests',source='sources/github/wests-cmd/kingdom',base_revision='a'*40,patch_sha256='b'*64)
        self.payload=dict(format='kingdom.patch-test.v1',receipt_id='receipt-1',reviewer_id='isolated-gate',issued_at=1000,expires_at=1200,binding=self.binding.copy(),execution=dict(run_id='run-1',image_sha256='c'*64,source_archive_sha256='d'*64,candidate_tree_sha256='e'*64,argv=['python','-m','pytest'],test_count=5,failed_count=0,exit_code=0,network_isolated=True,read_only_source=True))
        public=base64.b64encode(self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        self.reviewers={'isolated-gate':dict(public_key=public,enabled=True,projects=['kingdom'],sources=[self.binding['source']])}
    def signed(self,payload=None):
        value=deepcopy(payload or self.payload)
        return {'payload':value,'signature':base64.b64encode(self.key.sign(canonical(value))).decode()}
    def test_current_exact_patch_passes(self):
        result=verify_attestation(self.signed(),self.binding,self.reviewers,now=1100)
        self.assertEqual(result['execution']['test_count'],5)
    def test_every_binding_substitution_is_rejected(self):
        for field in self.binding:
            with self.subTest(field=field):
                expected=self.binding.copy();expected[field]=2 if field=='mission_version' else 'different'
                with self.assertRaises(ValueError):verify_attestation(self.signed(),expected,self.reviewers,now=1100)
    def test_signature_tamper_unsigned_flags_unknown_key_and_revocation_are_rejected(self):
        bad=self.signed();bad['payload']['execution']['test_count']=20
        for evidence,keys in [(bad,self.reviewers),({'accepted':True,'tests_passed':True},self.reviewers),(self.signed(),{}),(self.signed(),{'isolated-gate':{**self.reviewers['isolated-gate'],'enabled':False}})]:
            with self.assertRaises(ValueError):verify_attestation(evidence,self.binding,keys,now=1100)
    def test_expiry_failure_empty_suite_and_missing_isolation_are_rejected(self):
        for field,value in [('test_count',0),('test_count',True),('failed_count',1),('exit_code',1),('read_only_source',False),('network_isolated',False),('candidate_tree_sha256','')]:
            p=deepcopy(self.payload);p['execution'][field]=value
            with self.assertRaises(ValueError):verify_attestation(self.signed(p),self.binding,self.reviewers,now=1100)
        for now in [900,1200,2000]:
            with self.assertRaises(ValueError):verify_attestation(self.signed(),self.binding,self.reviewers,now=now)

if __name__=='__main__':unittest.main()
