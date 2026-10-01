"""Signed-interaction adapter over Kingdom services, without a parallel runtime."""
import asyncio
import json
import re
import time
from urllib.parse import urlsplit
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from backend.skills.portable import MAX_UPLOAD
from backend.integrations.public_apis import safe_get, REVIEWED


def message(content, components=None):
    data = {"content": content[:1900], "flags": 64, "allowed_mentions": {"parse": []}}
    if components:
        data["components"] = components
    return {"type": 4, "data": data}


class DiscordAdapter:
    def __init__(self, config, service, linker):
        self.config, self.service, self.linker = config, service, linker

    def verify(self, signature, timestamp, body):
        if not self.config.enabled or not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
            raise PermissionError("Discord request is disabled or expired")
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.config.public_key)).verify(
                bytes.fromhex(signature), timestamp.encode() + body)
        except Exception as exc:
            raise PermissionError("Invalid Discord request signature") from exc

    def route(self, interaction):
        if str(interaction.get("application_id")) != self.config.application_id:
            raise PermissionError("Wrong Discord application")
        if interaction.get("type") == 1:
            return {"type": 1}
        if self.config.guild_id and str(interaction.get("guild_id")) != self.config.guild_id:
            raise PermissionError("Discord server is not configured")
        user = interaction.get("member", {}).get("user") or interaction.get("user", {})
        user_id = str(user.get("id", ""))
        data = interaction.get("data", {})
        command = data.get("name")
        if command == "help":
            return message("Use /kingdom to link, then /status, /knights, /profiles, /skills, /skillmap import|export|test, /apis or /tasks. Kingdom permissions are required.")
        if command == "kingdom":
            challenge = self.linker.challenge(user_id)
            return message("Confirm this code in Kingdom → Skill maps & Discord within five minutes: " + challenge["code"])
        actor = self.linker.actor(user_id)
        if interaction.get("type") == 3:
            custom_id = data.get("custom_id", "")
            if not custom_id.startswith("map-confirm:"):
                raise ValueError("Unsupported component")
            preview_id = custom_id.split(":", 1)[1]
            pending = self.service.repository.get("map_preview", preview_id)
            if not pending:
                raise ValueError("Preview expired")
            result = self.service.confirm(actor, preview_id, pending["checksum"])
            return message("Saved preferences: " + result["map_id"] + ". No permissions or tools were installed.")
        permissions = {"status": "view_status", "knights": "view_knights", "profiles": "view_status",
                       "skills": "view_skills", "apis": "view_providers", "tasks": "run_task"}
        if command in permissions:
            self.service.authorize(actor, permissions[command])
        if command == "status":
            state = self.service.engine.status()
            return message("Kingdom runtime: " + ("running" if state.get("running") else "stopped"))
        if command == "knights":
            return message("\n".join(worker["display_name"] + ": " + worker["status"] for worker in self.service.engine.swarm.registry.status()))
        if command == "skills":
            return message(f"Kingdom holds {len(self.service.lifecycle.skills)} saved skill records. Imported maps are preferences.")
        if command == "profiles":
            options = {option["name"]: option.get("value") for option in data.get("options", [])}
            if options:
                self.service.set_profile_preferences(actor, options.get("profile_id"), options.get("map_id"))
            profiles = self.service.profiles(actor)
            selected = profiles["preferences"]
            text = "Available profiles: " + ", ".join(profile["name"] for profile in profiles["available"])
            if selected:
                text += "\nPreferred profile: " + selected["profile_id"] + "; map: " + selected["map_id"]
            return message(text + "\nPreferences do not change permissions or active workers.")
        if command == "apis":
            options = {option["name"]: option.get("value") for option in data.get("options", [])}
            if options:
                result = self.service.enable_provider(actor, options.get("provider_id"), options.get("enabled"))
                return message(result["provider_id"] + (": test enabled" if result["enabled"] else ": test disabled"))
            return message("Reviewed read-only adapters: " + ", ".join(REVIEWED) + ". Catalog entries are unverified discovery information.")
        if command == "tasks":
            lines = []
            records = [row for row in self.service.repository.list("map_test") if row["actor"] == actor][-10:]
            for row in records:
                task = self.service.engine.tasks.get(row["task_id"])
                if task:
                    lines.append(row["provider_id"] + ": " + task["status"])
            return message("\n".join(lines) or "No provider-test tasks for your identity.")
        if command != "skillmap":
            raise ValueError("Unsupported command")
        sub = (data.get("options") or [{}])[0]
        options = {option["name"]: option.get("value") for option in sub.get("options", [])}
        if sub.get("name") == "import":
            self.service.authorize(actor, "import_skillmaps")
            attachment = data.get("resolved", {}).get("attachments", {}).get(str(options.get("file")))
            if not attachment or not isinstance(attachment.get("size"), int) or attachment["size"] > MAX_UPLOAD:
                raise ValueError("Missing or oversized attachment")
            return {"deferred": "import", "actor": actor, "attachment": attachment}
        map_id = options.get("map_id")
        if not isinstance(map_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", map_id):
            raise ValueError("Map identifier required")
        if sub.get("name") == "test":
            result = self.service.submit_tests(actor, map_id)
            return message(f"Queued {len(result['tasks'])} governed tasks; {len(result['skipped'])} providers unsupported or disabled. Use /tasks to check progress.")
        if sub.get("name") == "export":
            self.service.authorize(actor, "export_skillmaps")
            return {"deferred": "export", "actor": actor, "map_id": map_id}
        raise ValueError("Unsupported skill-map action")

    def download_attachment(self, attachment):
        url = attachment.get("url", "")
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in {"cdn.discordapp.com", "media.discordapp.net"} or not parts.path.startswith("/attachments/"):
            raise ValueError("Only Discord attachment URLs are allowed")
        body, _ = safe_get(url, max_bytes=MAX_UPLOAD)
        return body

    async def deliver_interaction(self, interaction):
        try:
            action = await asyncio.to_thread(self.route, interaction)
        except (ValueError, PermissionError, KeyError, TypeError, OSError):
            action = message("Request could not be completed. Link your identity and check permissions, map schema and Kingdom state.")
        if "deferred" not in action:
            action = {"deferred": "message", "data": action.get("data", message("Unsupported interaction")["data"])}
        await self.deliver_deferred(interaction, action)

    async def deliver_deferred(self, interaction, action):
        token = interaction.get("token", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,300}", token):
            return
        url = f"https://discord.com/api/v10/webhooks/{self.config.application_id}/{token}"
        files = None
        try:
            if action["deferred"] == "message":
                payload = action["data"]
            elif action["deferred"] == "import":
                body = await asyncio.to_thread(self.download_attachment, action["attachment"])
                preview = self.service.preview(action["actor"], action["attachment"]["filename"], body)
                text = f"Map {preview['map_id']}: {preview['skills']} skills; {len(preview['unsupported_skills'])} unsupported. {len(preview['providers'])} provider requests; {len(preview['compatible_knights'])} compatible workers. Confirm preferences only."
                components = [{"type": 1, "components": [{"type": 2, "style": 1, "label": "Confirm import", "custom_id": "map-confirm:" + preview["preview_id"]}]}]
                payload = message(text, components)["data"]
            else:
                # Export remains available to export-only users; collection requires a separate grant.
                from backend.security.capabilities import CapabilityEvaluator
                caps = self.service.engine.security.nodes.get_node_capabilities(action["actor"])
                if CapabilityEvaluator.evaluate(caps, "test_skillmaps"):
                    self.service.collect_results(action["actor"], action["map_id"])
                result = self.service.export(action["actor"], action["map_id"])
                payload = message("Skill-map export. SHA-256: " + result["checksum"])["data"]
                payload["attachments"] = [{"id": 0, "filename": result["filename"]}]
                files = {"files[0]": (result["filename"], result["payload"], "application/json")}
        except (ValueError, PermissionError, KeyError, OSError):
            payload = message("Operation failed. Check permissions, schema, provider state and preview expiry in Kingdom.")["data"]
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                if files:
                    response = await client.post(url, data={"payload_json": json.dumps(payload)}, files=files)
                else:
                    response = await client.post(url, json=payload)
                if response.status_code not in (200, 201, 204):
                    self.service.engine.events.publish("discord.delivery_failed", {"status": response.status_code})
        except httpx.HTTPError:
            self.service.engine.events.publish("discord.delivery_failed", {"reason": "network_error"})
