import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('heartbeat_link', Path(__file__).parents[1] / 'scripts/peer-heartbeat-link.py')
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


class HeartbeatBoundaryTests(unittest.TestCase):
    def test_only_expected_identity_target_and_message_type(self):
        message = dict(sender_id='a', target_id='b', msg_type='heartbeat', protocol_version='kingdom.cluster.v1')
        self.assertEqual(link.validate_envelope(message, 'a', 'b', 'heartbeat'), message)
        for key, value in [('sender_id', 'other'), ('target_id', 'other'), ('msg_type', 'knight_management'), ('protocol_version', 'old')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                link.validate_envelope({**message, key: value}, 'a', 'b', 'heartbeat')

    def test_missing_or_non_object_response_rejected(self):
        for message in [None, [], {}, 'connected']:
            with self.subTest(message=message), self.assertRaises(ValueError):
                link.validate_envelope(message, 'a', 'b', 'inventory_snapshot')


if __name__ == '__main__':
    unittest.main()
