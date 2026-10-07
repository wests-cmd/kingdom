import unittest
from verify_android_signature import verify_identity
class SigningTests(unittest.TestCase):
    def test_legacy_and_sdk_range_signers(self):
        for label in ['V2 Signer:', 'V3 Signer:', 'Signer #1','Signer (minSdkVersion=24, maxSdkVersion=32)','Signer (minSdkVersion=33, maxSdkVersion=2147483647)']:
            self.assertEqual(verify_identity(label+' certificate SHA-256 digest: '+'a'*64+'\n','A'*64),'a'*64)
    def test_unknown_missing_or_multiple_identities_rejected(self):
        for output in ['', 'Signer #1 certificate SHA-256 digest: '+'b'*64, 'Signer #1 certificate SHA-256 digest: '+'a'*64+'\nSigner #2 certificate SHA-256 digest: '+'b'*64]:
            with self.assertRaises(ValueError):verify_identity(output,'a'*64)
if __name__=='__main__':unittest.main()
