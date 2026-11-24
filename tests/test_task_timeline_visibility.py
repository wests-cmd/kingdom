"""Owner-scoped task timeline never exposes event payloads or arbitrary model prose."""
import unittest
from unittest.mock import patch
from backend.main import app
from tests.auth_support import owner_client


class TaskTimelineVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.client = owner_client(app)

    def test_timeline_preserves_only_metadata_for_exact_task(self):
        rows = [
            {'event_id':'event-2','event_type':'task.completed','timestamp':1730000002,
             'task_id':'example-123','source':'worker','payload':{'token':'ghp_PRIVATE_DATA','prompt':'secret'}},
            {'event_id':'event-1','event_type':'task.queued','timestamp':1730000001,
             'task_id':'example-123','source':'system','payload':{'password':'should-never-appear'}}
        ]
        with patch('backend.api.engine.tasks.get',return_value={'id':'example-123','status':'completed'}), \
             patch('backend.storage.repository.event_repo.query',return_value=rows) as query:
            response=self.client.get('/tasks/example-123/timeline?limit=30')
        self.assertEqual(response.status_code,200)
        view=response.json()
        self.assertEqual([r['event_type'] for r in view['events']],['task.queued','task.completed'])
        self.assertEqual(list(view['events'][0]),['event_id','event_type','timestamp'])
        self.assertNotIn('ghp_PRIVATE_DATA',response.text)
        self.assertNotIn('password',response.text)
        query.assert_called_once_with(task_id='example-123',limit=31)

    def test_anonymous_cannot_read_other_task_events(self):
        from fastapi.testclient import TestClient
        from backend.security.http_auth import require_owner
        prior=app.dependency_overrides.pop(require_owner,None)
        try:
            response=TestClient(app).get('/tasks/example-123/timeline')
            self.assertIn(response.status_code,{401,403})
        finally:
            if prior is not None:
                app.dependency_overrides[require_owner]=prior

    def test_missing_task_has_no_timeline(self):
        with patch('backend.api.engine.tasks.get',return_value=None):
            self.assertEqual(self.client.get('/tasks/not-found/timeline').status_code,404)

    def test_invalid_limit_does_not_invoke_database(self):
        self.assertEqual(self.client.get('/tasks/example-123/timeline?limit=10000').status_code,422)

    def test_database_failure_not_reported_as_empty(self):
        with patch('backend.api.engine.tasks.get',return_value={'id':'example-123'}), \
             patch('backend.storage.repository.event_repo.query',side_effect=RuntimeError('no db')):
            res=self.client.get('/tasks/example-123/timeline')
        self.assertEqual(res.status_code,503)

    def test_truncation_and_cross_task_filter(self):
        rows=[
            {'event_id':'new','event_type':'task.completed','timestamp':3,'task_id':'example'},
            {'event_id':'other','event_type':'task.failed','timestamp':2,'task_id':'another'},
            {'event_id':'old','event_type':'task.queued','timestamp':1,'task_id':'example'}
        ]
        with patch('backend.api.engine.tasks.get',return_value={'id':'example'}), \
             patch('backend.storage.repository.event_repo.query',return_value=rows):
            res=self.client.get('/tasks/example/timeline?limit=2')
        self.assertEqual(res.status_code,200)
        self.assertTrue(res.json()['truncated'])
        self.assertEqual([r['event_id'] for r in res.json()['events']],['new'])



class NotificationVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.client=owner_client(app)

    def test_notification_history_exposes_only_allowlisted_event_metadata(self):
        rows=[
            {'event_id':'new','event_type':'task.completed','timestamp':3,'task_id':'task-1',
             'payload':{'secret':'PRIVATE_TOKEN'}},
            {'event_id':'ignored','event_type':'agent.prompt','timestamp':2,'task_id':'task-1',
             'payload':{'prompt':'EXFILTRATE_ME'}},
            {'event_id':'old','event_type':'task.failed','timestamp':1,'task_id':'task-2',
             'payload':{'api_key':'PRIVATE_KEY'}}
        ]
        with patch('backend.storage.repository.event_repo.query',return_value=rows) as query:
            response=self.client.get('/notifications?limit=10')
        self.assertEqual(response.status_code,200)
        self.assertEqual([x['event_id'] for x in response.json()],['old','new'])
        self.assertEqual(list(response.json()[0]),['event_id','event_type','timestamp','task_id'])
        for private in ('PRIVATE_TOKEN','EXFILTRATE_ME','PRIVATE_KEY','payload'):
            self.assertNotIn(private,response.text)
        query.assert_called_once_with(limit=300)

    def test_notifications_no_false_empty_state_when_database_fails(self):
        with patch('backend.storage.repository.event_repo.query',side_effect=RuntimeError('unavailable')):
            response=self.client.get('/notifications')
        self.assertEqual(response.status_code,503)

    def test_notification_limit_is_bounded(self):
        self.assertEqual(self.client.get('/notifications?limit=1000').status_code,422)

    def test_anonymous_notification_history_denied(self):
        from fastapi.testclient import TestClient
        from backend.security.http_auth import require_owner
        prior=app.dependency_overrides.pop(require_owner,None)
        try:
            response=TestClient(app).get('/notifications')
            self.assertIn(response.status_code,{401,403})
        finally:
            if prior is not None:
                app.dependency_overrides[require_owner]=prior


if __name__=='__main__':
    unittest.main()
