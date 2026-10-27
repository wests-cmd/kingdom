import os
import unittest
from backend.security.user_key_protection import PREFIX,protect_user_key,unprotect_user_key,key_file_lock


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

    @unittest.skipUnless(os.name=='nt','Windows byte-range locking regression')
    def test_empty_locked_file_is_not_written_before_acquiring_the_range(self):
        import msvcrt,time
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from threading import Event
        with TemporaryDirectory() as directory,ThreadPoolExecutor(max_workers=1) as pool:
            path=Path(directory)/'key.lock'
            with path.open('w+b',buffering=0) as first:
                msvcrt.locking(first.fileno(),msvcrt.LK_LOCK,1)
                started=Event()
                def acquire():
                    started.set()
                    with key_file_lock(path):return True
                future=pool.submit(acquire)
                try:
                    self.assertTrue(started.wait(2))
                    time.sleep(.05)
                    self.assertFalse(future.done(),'A competing initializer must wait, not write into the locked range')
                    self.assertEqual(path.stat().st_size,0)
                finally:
                    first.seek(0);msvcrt.locking(first.fileno(),msvcrt.LK_UNLCK,1)
                self.assertTrue(future.result(timeout=3))

if __name__=='__main__':unittest.main()
