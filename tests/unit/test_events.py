import unittest
from backend.events.event_bus import EventBus

class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()

    def test_event_publish_subscribe_and_query(self):
        received = []
        def handler(evt):
            received.append(evt)

        self.bus.subscribe(handler)
        evt = self.bus.publish("task.created", {"task_id": "123"}, source="unit_test", task_id="123")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["event_type"], "task.created")

        history = self.bus.get_events(task_id="123")
        self.assertTrue(any(e["event_id"] == evt["event_id"] for e in history))

    def test_task_events_bind_indexed_identity_for_persistent_timeline(self):
        saved=[]
        class RecordingRepo:
            def save(self,event):
                saved.append(event)
        bus=EventBus(repository=RecordingRepo())
        task=bus.publish('task.queued', {'id':'task-42','prompt':'do not put this in timeline'})
        self.assertEqual(task['task_id'],'task-42')
        self.assertEqual(saved[0]['task_id'],'task-42')
        self.assertNotIn('task_id',task['payload'].get('prompt',''))
        explicit=bus.publish('task.completed', {'id':'untrusted'}, task_id='explicit')
        self.assertEqual(explicit['task_id'],'explicit')
        unrelated=bus.publish('runtime.started', {'id':'runtime'})
        self.assertIsNone(unrelated['task_id'])
        malformed=bus.publish('task.failed', {'id':123})
        self.assertIsNone(malformed['task_id'])


if __name__ == "__main__":
    unittest.main()
