"""Discord possession plus explicit owner approval; guild membership grants nothing."""
import hashlib
import secrets
import time
from backend.security.capabilities import ALL_CAPABILITIES

DISCORD_GRANTS = {"view_status", "view_knights", "view_skills", "import_skillmaps", "export_skillmaps",
                  "test_skillmaps", "view_providers", "manage_providers", "run_task", "providers.test"}


class DiscordIdentityLinker:
    def __init__(self, service):
        self.service = service
        self.repository = service.repository
        for link in self.repository.list("discord_link"):
            if not link.get("revoked"):
                self._register(link)

    def _register(self, link):
        self.service.engine.security.nodes.register_node(link["actor"], name="Linked Discord user",
                                                         capabilities=set(link["grants"]))

    def challenge(self, user_id):
        if not str(user_id).isdigit() or len(str(user_id)) > 30:
            raise ValueError("Invalid Discord identity")
        code = secrets.token_urlsafe(24)
        digest = hashlib.sha256(code.encode()).hexdigest()
        self.repository.put("discord_challenge", digest,
            {"user_id": str(user_id), "expires_at": time.time() + 300})
        return {"code": code, "expires_in": 300, "notice": "Confirm this code in Kingdom. No permissions are granted yet."}

    def confirm(self, owner, code, grants):
        self.service.authorize(owner, "system.admin")
        if not set(grants).issubset(DISCORD_GRANTS & ALL_CAPABILITIES):
            raise ValueError("Unsupported Discord permission")
        digest = hashlib.sha256(code.encode()).hexdigest()
        with self.repository.db.get_connection() as conn:
            import json
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM integration_records WHERE kind='discord_challenge' AND id=?", (digest,)).fetchone()
            challenge = json.loads(row[0]) if row else None
            if not challenge or challenge["expires_at"] < time.time():
                raise PermissionError("Link challenge expired or already used")
            user_id = challenge["user_id"]
            link = {"user_id": user_id, "actor": "discord-" + user_id, "grants": sorted(set(grants)), "revoked": False}
            conn.execute("INSERT INTO integration_records VALUES('discord_link',?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (user_id, json.dumps(link), time.time()))
            conn.execute("DELETE FROM integration_records WHERE kind='discord_challenge' AND id=?", (digest,))
        self._register(link)
        self.service.engine.events.publish("discord.identity_linked", {"permission_count": len(grants)})
        return link

    def actor(self, user_id):
        link = self.repository.get("discord_link", str(user_id))
        if not link or link.get("revoked"):
            raise PermissionError("Link your Discord identity in Kingdom first")
        return link["actor"]

    def revoke(self, owner, user_id):
        self.service.authorize(owner, "system.admin")
        link = self.repository.get("discord_link", user_id)
        if not link:
            raise KeyError("Discord identity not linked")
        link["revoked"] = True
        self.repository.put("discord_link", user_id, link)
        self.service.engine.security.nodes.revoke_node(link["actor"])
        self.service.engine.events.publish("discord.identity_revoked", {"state": "revoked"})
        return {"state": "revoked"}
