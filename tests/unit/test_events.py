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

if __name__ == "__main__":
    unittest.main()
