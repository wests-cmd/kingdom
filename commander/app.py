from fastapi import FastAPI
from commander.orchestrator import Orchestrator
from system.task_queue import TaskQueue

app = FastAPI(title="Kingdom")

queue = TaskQueue()
orchestrator = Orchestrator(queue)

@app.post("/task")
def create_task(task: dict):
    queue.add(task)
    return {"status": "queued"}

@app.get("/task")
def get_task():
    return queue.get()

@app.post("/result")
def result(data: dict):
    orchestrator.handle_result(data)
    return {"status": "received"}
