"""Harness-neutral SKILL.md transport. Documents are context, never authority."""
import hashlib
import json
import re
import secrets
import time
from typing import Literal

import yaml
from pydantic import Field

from backend.skills.portable import Identifier, StrictModel, UniqueSafeLoader, MAX_UPLOAD


class Provenance(StrictModel):
    source: str = Field(default="manual", min_length=1, max_length=500)
    harness: Identifier = "generic"
    sha256: str = Field(pattern="^[0-9a-f]{64}$")


class SkillDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    skill_id: Identifier
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    instructions: str = Field(min_length=1, max_length=250000)
    provenance: Provenance
    trust: Literal["untrusted"] = "untrusted"
    execution_enabled: Literal[False] = False


def parse_document(content: str, source="manual", harness="generic") -> SkillDocument:
    if not content or len(content.encode("utf-8")) > MAX_UPLOAD or "\x00" in content:
        raise ValueError("Skill document must be bounded UTF-8 text")
    match = re.match(r"\A\ufeff?---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", content, re.S)
    if not match:
        raise ValueError("SKILL.md requires YAML name and description frontmatter")
    header, body = match.groups()
    try:
        tokens = list(yaml.scan(header))
        if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken)) for token in tokens):
            raise ValueError("YAML aliases and tags are not supported")
        metadata = yaml.load(header, Loader=UniqueSafeLoader)
        if not isinstance(metadata, dict):
            raise ValueError("Frontmatter must be a mapping")
        # Harness-specific metadata such as allowed-tools is deliberately not interpreted.
        name, description = metadata.get("name"), metadata.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise ValueError("Name and description must be text")
        return SkillDocument(skill_id=name, name=name, description=description,
            instructions=body.strip(), provenance=Provenance(source=source, harness=harness,
                sha256=hashlib.sha256(content.encode()).hexdigest()))
    except (yaml.YAMLError, RecursionError, TypeError) as exc:
        raise ValueError("Malformed skill frontmatter") from exc


def export_document(document: SkillDocument) -> str:
    # Only portable fields are emitted; tool permission hints cannot become grants.
    header = yaml.safe_dump({"name": document.name, "description": document.description}, sort_keys=False).strip()
    return f"---\n{header}\n---\n\n{document.instructions}\n"


class SkillDocumentService:
    def __init__(self, portable_service):
        self.portable = portable_service
        self.repository = portable_service.repository

    def preview(self, actor, content, source="manual", harness="generic"):
        self.portable.authorize(actor, "import_skillmaps")
        document = parse_document(content, source, harness)
        payload = document.model_dump_json()
        checksum = hashlib.sha256(payload.encode()).hexdigest()
        ident = secrets.token_urlsafe(24)
        self.repository.put("skill_document_preview", ident, {"actor": actor, "payload": payload,
            "checksum": checksum, "expires_at": time.time() + 300})
        self.portable.engine.events.publish("skill_document.previewed", {"skill_id": document.skill_id})
        return {"preview_id": ident, "checksum": checksum, "document": document.model_dump(),
            "notice": "Untrusted instructions only. Import neither executes code, installs tools nor grants permissions."}

    def confirm(self, actor, preview_id, checksum):
        self.portable.authorize(actor, "import_skillmaps")
        with self.repository.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value_json FROM integration_records WHERE kind='skill_document_preview' AND id=?", (preview_id,)).fetchone()
            pending = json.loads(row[0]) if row else None
            if not pending or pending["actor"] != actor or pending["expires_at"] < time.time() or not secrets.compare_digest(pending["checksum"], checksum):
                raise PermissionError("Import preview expired, changed or belongs to another identity")
            document = SkillDocument.model_validate_json(pending["payload"])
            record = {"actor": actor, "skill_id": document.skill_id, "document": document.model_dump(), "checksum": checksum}
            conn.execute("INSERT INTO integration_records VALUES('skill_document',?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (actor + ":" + document.skill_id, json.dumps(record), time.time()))
            conn.execute("DELETE FROM integration_records WHERE kind='skill_document_preview' AND id=?", (preview_id,))
        self.portable.engine.events.publish("skill_document.imported", {"skill_id": document.skill_id, "trust": "untrusted"})
        return {"skill_id": document.skill_id, "checksum": checksum, "state": "saved_untrusted_context"}

    def export(self, actor, skill_id):
        self.portable.authorize(actor, "export_skillmaps")
        row = self.repository.get("skill_document", actor + ":" + skill_id)
        if not row:
            raise KeyError("Skill document not found")
        document = SkillDocument.model_validate(row["document"])
        return {"filename": "SKILL.md", "content": export_document(document), "document": document.model_dump()}
