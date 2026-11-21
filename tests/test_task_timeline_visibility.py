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


if __name__=='__main__':
    unittest.main()
