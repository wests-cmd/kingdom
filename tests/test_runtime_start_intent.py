import asyncio
from backend.runtime.engine import RuntimeEngine
from backend.runtime.policy import ExecutionPolicy
from backend.storage.db import Database

def test_owner_start_intent_survives_graceful_shutdown_and_explicit_stop(tmp_path):
 engine=RuntimeEngine();database=Database(tmp_path/'intent.db');engine.execution_policy=ExecutionPolicy(database)
 assert engine.autostart_requested() is False
 engine.execution_policy.set(0)
 async def scenario():
  await engine.start()
  assert engine.autostart_requested() is True
  await engine.stop(persist=False)
  assert engine.autostart_requested() is True
  restored=RuntimeEngine();restored.execution_policy=ExecutionPolicy(database)
  assert restored.autostart_requested() is True
  await restored.start(persist=False)
  await restored.stop()
  assert engine.autostart_requested() is False
 asyncio.run(scenario())
