import os
import unittest
from backend.security.user_key_protection import PREFIX,protect_user_key,unprotect_user_key


class UserKeyProtectionTests(unittest.TestCase):
    def test_current_user_round_trip(self):
        value=b'ephemeral-test-key-material-not-an-account-key'
        envelope=protect_user_key(value)
        self.assertEqual(unprotect_user_key(envelope),value)
        if os.name=='nt':
            self.assertTrue(envelope.startswith(PREFIX))
            self.assertNotIn(value,envelope)
            with self.assertRaises(OSError):unprotect_user_key(PREFIX+b'not-a-dpapi-envelope')
    def test_empty_and_oversized_keys_are_rejected(self):
        for value in [b'',b'x'*65537,'not bytes']:
            with self.assertRaises(ValueError):protect_user_key(value)

if __name__=='__main__':unittest.main()
