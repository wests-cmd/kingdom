import time
from backend.swarm.task_queue import TaskQueue
from backend.swarm.workload_balancer import WorkloadBalancer
from backend.swarm.scoring import SwarmScoring
from backend.security.prompt_firewall import PromptFirewall
from backend.security.zero_trust import ZeroTrust
from backend.security.approval_engine import approval_engine
from backend.security.audit_log import audit_logger
from backend.storage.repository import task_repo, knight_repo
from backend.events.event_bus import event_bus

class SwarmEngine:

    def __init__(self, firewall=None, zero_trust=None, approval_eng=None, logger=None):
        self.queue = TaskQueue()
        self.balancer = WorkloadBalancer()
        self.scoring = SwarmScoring()
        self.firewall = firewall or PromptFirewall()
        self.zero_trust = zero_trust or ZeroTrust()
        self.approval_engine = approval_eng or approval_engine
        self.audit_logger = logger or audit_logger

    def submit_task(self, task):
        if isinstance(task, dict) and "id" in task:
            task_repo.save(task)
        self.queue.add(task)

    def process(self):
        task = self.queue.next()

        if not task:
            # Check DB for queued tasks
            queued_tasks = task_repo.list_all(status="queued", limit=1)
            if queued_tasks:
                task = queued_tasks[0]
            else:
                return None

        # Normalize task object
        if isinstance(task, str):
            task_obj = {
                "id": str(time.time()),
                "content": task,
                "input": {"content": task},
                "actor": {"id": "default_user", "role": "knight", "verified": True},
                "capability": "model.inference",
                "action": "infer",
                "status": "queued"
            }
        elif isinstance(task, dict):
            task_obj = task
        else:
            task_obj = {"id": str(time.time()), "content": str(task), "actor": None, "capability": "model.inference", "action": "infer", "status": "queued"}

        task_id = task_obj.get("id")
        actor = task_obj.get("actor") or {"id": "guest", "role": "guest", "verified": False}
        actor_id = actor.get("id", "unknown") if isinstance(actor, dict) else str(actor)
        capability = task_obj.get("capability", "model.inference")
        action = task_obj.get("action", "execute")
        input_data = task_obj.get("input") or {"content": task_obj.get("content", "")}
        content = input_data.get("content", str(input_data)) if isinstance(input_data, dict) else str(input_data)
        approval_id = task_obj.get("approval_id")

        # Check cancellation
        if task_obj.get("cancellation_requested"):
            task_obj["status"] = "cancelled"
            task_repo.save(task_obj)
            event_bus.publish("task.cancelled", task_obj, source="swarm_engine", task_id=task_id)
            return task_obj

        # 1. Prompt Injection Inspection
        try:
            self.firewall.inspect(content)
        except Exception as e:
            task_obj["status"] = "failed"
            task_obj["error"] = f"Prompt firewall block: {e}"
            task_repo.save(task_obj)
            self.audit_logger.log_event(
                actor=actor_id,
                node=task_obj.get("node_id", "local"),
                operation=action,
                capability=capability,
                decision="blocked",
                reason=f"Prompt injection detected: {e}"
            )
            event_bus.publish("task.failed", task_obj, source="swarm_engine", task_id=task_id)
            return task_obj

        # 2. Zero-Trust Capability Check
        zt_result = self.zero_trust.validate(actor, required_capability=capability)
        if not zt_result.get("authorized"):
            reason = zt_result.get("reason", "Unauthorized")
            task_obj["status"] = "failed"
            task_obj["error"] = reason
            task_repo.save(task_obj)
            self.audit_logger.log_event(
                actor=actor_id,
                node=task_obj.get("node_id", "local"),
                operation=action,
                capability=capability,
                decision="denied",
                reason=reason
            )
            event_bus.publish("task.failed", task_obj, source="swarm_engine", task_id=task_id)
            return task_obj

        # 3. Risk Classification & Approval Gate
        risk_level = self.approval_engine.classify_risk(capability=capability, action=action)
        requires_app = self.approval_engine.requires_approval(capability=capability, action=action)

        if requires_app:
            approved = False
            if approval_id:
                app_req = self.approval_engine.get_request(approval_id)
                if app_req and app_req.get("status") == "approved":
                    approved = True

            if not approved:
                app_req = self.approval_engine.create_request(
                    requesting_node=task_obj.get("node_id", "local"),
                    component="swarm_engine",
                    requested_capability=capability,
                    action=action,
                    reason=f"Task requires elevated authorization ({risk_level} risk)",
                    risk_level=risk_level,
                    parameters={"content": content}
                )
                task_obj["status"] = "queued" # Remains queued until approved
                task_repo.save(task_obj)
                self.audit_logger.log_event(
                    actor=actor_id,
                    node=task_obj.get("node_id", "local"),
                    operation=action,
                    capability=capability,
                    decision="approval_required",
                    reason=f"Operation requires human approval (Risk: {risk_level})",
                    approval_id=app_req["approval_id"]
                )
                event_bus.publish("governance.approval_required", app_req, source="swarm_engine", task_id=task_id)
                return {
                    "task": task_obj,
                    "status": "pending_approval",
                    "approval_id": app_req["approval_id"],
                    "risk_level": risk_level,
                    "reason": "Operation paused pending human approval"
                }

        # 4. Knight Selection & Execution
        knight = self.balancer.select_knight(task_obj)
        task_obj["assigned_knight"] = knight
        task_obj["status"] = "assigned"
        task_repo.save(task_obj)
        event_bus.publish("task.assigned", task_obj, source="swarm_engine", task_id=task_id)

        task_obj["status"] = "running"
        task_repo.save(task_obj)
        event_bus.publish("task.started", task_obj, source="swarm_engine", task_id=task_id)

        score = self.scoring.score_task(task_obj)
        task_obj["status"] = "completed"
        task_obj["result"] = {"output": f"Executed by {knight}", "score": score}
        task_repo.save(task_obj)

        self.audit_logger.log_event(
            actor=actor_id,
            node=task_obj.get("node_id", "local"),
            operation=action,
            capability=capability,
            decision="authorized",
            reason="Execution completed",
            approval_id=approval_id
        )

        event_bus.publish("task.completed", task_obj, source="swarm_engine", task_id=task_id)
        return task_obj
