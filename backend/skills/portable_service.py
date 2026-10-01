"""Shared portable-map workflow used by HTTP and Discord adapters."""
import hashlib
import json
import secrets
import time
from backend.skills.portable import parse_map, canonical_map, map_checksum, ProviderEvidence
from backend.integrations.public_apis import REVIEWED
from backend.storage.integration_repository import IntegrationRepository


class PortableMapService:
    def __init__(self, engine, lifecycle_manager, repository=None):
        self.engine = engine
        self.lifecycle = lifecycle_manager
        self.repository = repository or IntegrationRepository()

    def authorize(self, actor, capability):
        node = self.engine.security.nodes.get_node(actor)
        if not node or not node.get("active"):
            raise PermissionError("Identity is not active")
        from backend.security.capabilities import CapabilityEvaluator
        if not CapabilityEvaluator.evaluate(node["capabilities"], capability):
            raise PermissionError("Required Kingdom permission is not granted")

    def profiles(self, actor):
        self.authorize(actor, "view_status")
        catalog = self._profile_catalog()
        return {"available": [{"profile_id": key, "name": value["name"], "knights": value["knights"]}
                              for key, value in catalog["profiles"].items()],
                "preferences": self.repository.get("profile_preferences", actor),
                "notice": "Preferences rank eligible installed workers; they do not change installation or permissions."}

    @staticmethod
    def _profile_catalog():
        from pathlib import Path
        return json.loads((Path(__file__).parents[2] / "configs/install_profiles.json").read_text(encoding="utf-8"))

    def enable_provider(self, actor, provider_id, enabled):
        self.authorize(actor, "manage_providers")
        if provider_id not in REVIEWED or type(enabled) is not bool:
            raise ValueError("Provider has no reviewed executable adapter")
        self.repository.put("provider_settings", provider_id, {"provider_id": provider_id, "enabled": enabled})
        self.engine.events.publish("provider.settings_updated", {"provider_id": provider_id, "enabled": enabled})
        return {"provider_id": provider_id, "enabled": enabled}

    def set_profile_preferences(self, actor, profile_id, map_id):
        self.authorize(actor, "import_skillmaps")
        if profile_id not in {row["profile_id"] for row in self.profiles(actor)["available"]}:
            raise ValueError("Unknown installation profile")
        self.get(actor, map_id)
        preferences = {"actor": actor, "profile_id": profile_id, "map_id": map_id}
        self.repository.put("profile_preferences", actor, preferences)
        self.engine.events.publish("profile.preferences_updated", {"map_id": map_id})
        return preferences

    def preview(self, actor, filename, payload):
        self.authorize(actor, "import_skillmaps")
        model = parse_map(filename, payload)
        encoded = canonical_map(model)
        pending_id = secrets.token_urlsafe(24)
        checksum = hashlib.sha256(encoded).hexdigest()
        self.repository.put("map_preview", pending_id, {"id": pending_id, "actor": actor,
            "payload": encoded.decode(), "checksum": checksum, "expires_at": time.time() + 300})
        installed = {skill.id for skill in self.lifecycle.skill_map.list_skills()} if hasattr(self.lifecycle, "skill_map") else set()
        providers = [{"provider_id": provider.provider_id,
            "reviewed": provider.provider_id in REVIEWED,
            "credential_required": provider.credential_ref is not None,
            "requested_capabilities": provider.capabilities,
            "supported_capabilities": REVIEWED.get(provider.provider_id, {}).get("capabilities", [])}
            for provider in model.providers]
        understood = set().union(*(set(REVIEWED.get(provider.provider_id, {}).get("capabilities", [])) for provider in model.providers)) if model.providers else set()
        return {"preview_id": pending_id, "checksum": checksum, "map_id": model.map_id,
                "skills": len(model.skills), "understood_skills": sorted(installed & {s.skill_id for s in model.skills}),
                "unsupported_skills": sorted({s.skill_id for s in model.skills} - installed),
                "understood_capabilities": sorted(set(model.capabilities) & understood),
                "unsupported_capabilities": sorted(set(model.capabilities) - understood),
                "providers": providers, "compatible_knights": self.compatible_knights(),
                "notice": "Import saves preferences. It does not install tools or grant permissions."}

    def compatible_knights(self):
        return [role for role, knight in self.engine.swarm.registry._knights.items()
                if "providers.test" in knight.zero_trust.nodes.get_node_capabilities(role)
                and "providers.test" in self.engine.security.nodes.get_node_capabilities(role)
                and knight.health == "healthy" and knight.current_task is None
                and not self.engine.swarm.registry._active[role]]

    def preferred_knights(self, actor, model):
        eligible = self.compatible_knights()
        hints = list(model.preferred_resources)
        preference = self.repository.get("profile_preferences", actor)
        if preference and preference.get("map_id") == model.map_id:
            profile = self._profile_catalog()["profiles"].get(preference.get("profile_id"), {})
            hints.extend(profile.get("knights", []))
        ranked = list(dict.fromkeys(role for role in hints if role in eligible))
        return ranked + [role for role in eligible if role not in ranked]

    def confirm(self, actor, preview_id, checksum):
        self.authorize(actor, "import_skillmaps")
        # Transaction makes confirmation single-use even under concurrent component clicks.
        with self.repository.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM integration_records WHERE kind='map_preview' AND id=?", (preview_id,)).fetchone()
            pending = json.loads(row[0]) if row else None
            if not pending or pending["actor"] != actor or pending["expires_at"] < time.time() or not secrets.compare_digest(pending["checksum"], checksum):
                raise PermissionError("Import preview expired, changed or belongs to another identity")
            model = parse_map("import.json", pending["payload"].encode())
            key = actor + ":" + model.map_id
            record = {"actor": actor, "map_id": model.map_id, "payload": pending["payload"], "checksum": checksum}
            conn.execute("INSERT INTO integration_records VALUES('portable_map',?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (key, json.dumps(record), time.time()))
            conn.execute("DELETE FROM integration_records WHERE kind='map_preview' AND id=?", (preview_id,))
        self.engine.events.publish("skillmap.imported", {"map_id": model.map_id, "skill_count": len(model.skills)})
        return {"map_id": model.map_id, "checksum": checksum, "state": "saved_preferences"}

    def get(self, actor, map_id):
        record = self.repository.get("portable_map", actor + ":" + map_id)
        if not record:
            raise KeyError("Map not found for this identity")
        return parse_map("stored.json", record["payload"].encode())

    def export(self, actor, map_id):
        self.authorize(actor, "export_skillmaps")
        model = self.get(actor, map_id)
        return {"filename": model.map_id + ".skillmap.json", "payload": canonical_map(model), "checksum": map_checksum(model)}

    def submit_tests(self, actor, map_id):
        for capability in ("test_skillmaps", "run_task", "providers.test"):
            self.authorize(actor, capability)
        model = self.get(actor, map_id)
        knights = self.preferred_knights(actor, model)
        if not knights:
            raise ValueError("No available worker has the reviewed provider-test permission")
        tasks, skipped = [], [{"provider_id": p.provider_id, "status": "unsupported"} for p in model.providers[model.constraints.max_tests:]]
        for provider in model.providers[:model.constraints.max_tests]:
            spec = REVIEWED.get(provider.provider_id)
            settings = self.repository.get("provider_settings", provider.provider_id)
            if not spec or provider.credential_ref or not set(provider.capabilities).issubset(spec["capabilities"]):
                skipped.append({"provider_id": provider.provider_id, "status": "unsupported"})
                continue
            if not settings or not settings.get("enabled"):
                skipped.append({"provider_id": provider.provider_id, "status": "disabled"})
                continue
            task = self.engine.submit_task("Read reviewed public provider metadata", {
                "actor": actor, "capability": "providers.test", "tool": "provider.metadata@1.0.0",
                "tool_parameters": {"provider_id": provider.provider_id, "timeout_seconds": model.constraints.timeout_seconds}, "requested_knight": knights[0],
                "skillmap_id": map_id})
            task_id = task["id"]
            self.repository.put("map_test", task_id, {"actor": actor, "map_id": map_id,
                "provider_id": provider.provider_id, "task_id": task_id})
            tasks.append({"task_id": task_id, "provider_id": provider.provider_id, "status": task["status"]})
        return {"tasks": tasks, "skipped": skipped, "notice": "Tasks follow the current autonomy and approval policy."}

    def collect_results(self, actor, map_id):
        self.authorize(actor, "test_skillmaps")
        model = self.get(actor, map_id)
        # Imported verification fields are portable claims, not locally verified task evidence.
        evidence = {}
        states = []
        for record in self.repository.list("map_test"):
            if record["actor"] != actor or record["map_id"] != map_id:
                continue
            task = self.engine.tasks.get(record["task_id"])
            if not task:
                continue
            if task.get("metadata", {}).get("actor") != actor or task.get("metadata", {}).get("skillmap_id") != map_id:
                continue
            states.append({"task_id": task["id"], "status": task["status"], "provider_id": record["provider_id"]})
            if task["status"].lower() == "completed":
                results = (task.get("result") or {}).get("results", [])
                if results and all(result.get("verification", {}).get("state") == "VERIFIED" for result in results):
                    from backend.runtime.execution import verify_request_result
                    for result in results:
                        verify_request_result(task, result["outcome"])
                    summary = results[0]["outcome"]["output"]["summary"]
                    evidence[record["provider_id"]] = ProviderEvidence(provider_id=record["provider_id"], status="verified", response_sha256=summary["response_sha256"], capabilities=summary["capabilities"])
            elif task["status"].lower() == "failed":
                evidence[record["provider_id"]] = ProviderEvidence(provider_id=record["provider_id"], status="failed")
        portable_evidence = {item.provider_id: item for item in model.test_results}
        portable_evidence.update(evidence)
        model.test_results = list(portable_evidence.values())
        payload = canonical_map(model)
        self.repository.put("portable_map", actor + ":" + map_id, {"actor": actor, "map_id": map_id,
                            "payload": payload.decode(), "checksum": hashlib.sha256(payload).hexdigest()})
        return {"tasks": states, "results": [item.model_dump(exclude_none=True) for item in evidence.values()],
                "notice": "Only local governed tasks appear as verified results. Imported evidence remains an untrusted portable claim."}
