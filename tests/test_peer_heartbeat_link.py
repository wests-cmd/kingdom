import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('heartbeat_link', Path(__file__).parents[1] / 'scripts/peer-heartbeat-link.py')
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


class HeartbeatBoundaryTests(unittest.TestCase):
    def test_native_analysis_opt_in_never_exposes_other_execution(self):
        config={'identity':{'node_id':'controller'}}
        message={'target_id':'controller','msg_type':'task_poll','payload':{
            'require_running':True,'supported_tools':['text.analyze@1.0.0']}}
        with self.assertRaises(ValueError):link.validate_mesh_rpc(message,config)
        config['analysis_enabled']=True
        link.validate_mesh_rpc(message,config)
        for tool in ('process.run@1.0.0','build.run@1.0.0','workspace.read@1.0.0'):
            with self.subTest(tool=tool),self.assertRaises(ValueError):
                link.validate_mesh_rpc({**message,'payload':{'require_running':True,'supported_tools':[tool]}},config)
        for kind in ('knight_management','group_task_assign','task_submit'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):link.validate_mesh_rpc({**message,'msg_type':kind},config)
        with self.assertRaises(ValueError):link.validate_mesh_rpc({**message,'payload':{'supported_tools':['text.analyze@1.0.0']}},config)
        with self.assertRaises(ValueError):link.validate_mesh_rpc({'target_id':'controller','msg_type':'task_result','payload':{
            'status':'completed','output':{'kind':'native_tool','tool':'process.run@1.0.0'}}},config)
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

    def test_local_session_preserves_owner_passcode(self):
        config={'local':'http://127.0.0.1:8000','auth_mode':'local_session'}
        with patch.object(link,'request',return_value={'passcode_enabled':True}) as request:
            with self.assertRaises(ValueError):link.local_client(config)
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[0],'http://127.0.0.1:8000/auth/local/status')

    def test_owner_session_never_uses_remote_origin(self):
        for origin in ['http://192.168.1.2:8000','https://127.0.0.1:8000','http://127.0.0.1:8000/path','http://owner@127.0.0.1:8000']:
            with self.subTest(origin=origin),self.assertRaises(ValueError):
                link.local_client({'local':origin,'auth_mode':'local_session'})


if __name__ == '__main__':
    unittest.main()
