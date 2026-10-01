"""Portable preferences, never executable instructions or security grants."""
import hashlib
import json
import re
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,63}$", max_length=64)]
Text = Annotated[str, StringConstraints(max_length=500)]
MAX_UPLOAD = 262144


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProviderRequirement(StrictModel):
    provider_id: Identifier
    capabilities: list[Identifier] = Field(default_factory=list, max_length=30)
    credential_ref: Identifier | None = None
    required: bool = True


class PortableSkill(StrictModel):
    skill_id: Identifier
    capabilities: list[Identifier] = Field(default_factory=list, max_length=30)
    provider_ids: list[Identifier] = Field(default_factory=list, max_length=30)


class MapConstraints(StrictModel):
    read_only: Literal[True] = True
    timeout_seconds: int = Field(default=10, ge=1, le=15)
    max_tests: int = Field(default=5, ge=1, le=10)

    @field_validator("read_only", mode="before")
    @classmethod
    def must_be_readonly(cls, value):
        if value is not True:
            raise ValueError("Only a literal read-only preference is supported")
        return value


class MapMetadata(StrictModel):
    title: Text = "Untitled skill map"
    author: Text = ""
    description: Text = ""
    created_at: Text | None = None


class ProviderEvidence(StrictModel):
    provider_id: Identifier
    status: Literal["verified", "failed", "unsupported", "disabled"]
    response_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")] | None = None
    capabilities: list[Identifier] = Field(default_factory=list, max_length=30)


class PortableSkillMap(StrictModel):
    schema_version: Literal["1.0"]
    map_id: Identifier
    capabilities: list[Identifier] = Field(default_factory=list, max_length=100)
    skills: list[PortableSkill] = Field(default_factory=list, max_length=100)
    providers: list[ProviderRequirement] = Field(default_factory=list, max_length=100)
    preferred_resources: list[Identifier] = Field(default_factory=list, max_length=30)
    constraints: MapConstraints = Field(default_factory=MapConstraints)
    metadata: MapMetadata = Field(default_factory=MapMetadata)
    test_results: list[ProviderEvidence] = Field(default_factory=list, max_length=100)


UNSAFE = re.compile(r"(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{10,}|bearer\s+\S+|-----BEGIN|"
                    r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
                    r"(?:password|api[_ -]?key|secret|token)\s*[:=]\s*\S+|"
                    r"https?://|(?:\b(?:exec|eval|print|__import__)\s*\(|\b(?:import|from)\s+\w+|\bdef\s+\w+\s*\(|\bfunction\s*\w*\s*\(|=>|<script|\$\(|`)", re.I)


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


class UniqueSafeLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node):
    return _no_duplicates(loader.construct_pairs(node, deep=True))


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def parse_map(filename: str, payload: bytes) -> PortableSkillMap:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. ()-]{0,100}\.(?:json|yaml|yml)", filename, re.I) or ".." in filename:
        raise ValueError("Use a plain JSON or YAML filename without paths")
    if not payload or len(payload) > MAX_UPLOAD:
        raise ValueError("Skill maps must contain 1 to 262144 bytes")
    try:
        text = payload.decode("utf-8")
        if UNSAFE.search(text) or "\x00" in text:
            raise ValueError("Secrets, endpoints and executable instructions are not portable preferences")
        if filename.lower().endswith(".json"):
            value = json.loads(text, object_pairs_hook=_no_duplicates,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))
        else:
            # Block aliases and tags before safe_load: bounded bytes alone do not bound expansion.
            tokens = list(yaml.scan(text))
            if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken)) for token in tokens):
                raise ValueError("YAML aliases and tags are not supported")
            value = yaml.load(text, Loader=UniqueSafeLoader)
        model = PortableSkillMap.model_validate(value)
        for items, attr in ((model.skills, "skill_id"), (model.providers, "provider_id"), (model.test_results, "provider_id")):
            ids = [getattr(item, attr) for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate skill or provider identifier")
        known = {p.provider_id for p in model.providers}
        if any(set(skill.provider_ids) - known for skill in model.skills):
            raise ValueError("Skill refers to an undeclared provider")
        if any(result.provider_id not in known for result in model.test_results):
            raise ValueError("Evidence refers to an undeclared provider")
        return model
    except (RecursionError, UnicodeError, yaml.YAMLError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Malformed skill map") from exc


def canonical_map(model: PortableSkillMap) -> bytes:
    data = model.model_dump(exclude_none=True)
    data["metadata"].pop("created_at", None)  # Export time is not semantic identity.
    for field in ("capabilities", "preferred_resources"):
        data[field] = sorted(set(data[field]))
    data["skills"] = sorted(data["skills"], key=lambda s: s["skill_id"])
    data["providers"] = sorted(data["providers"], key=lambda p: p["provider_id"])
    data["test_results"] = sorted(data["test_results"], key=lambda p: p["provider_id"])
    for item in data["skills"] + data["providers"] + data["test_results"]:
        item["capabilities"] = sorted(set(item["capabilities"]))
        if "provider_ids" in item:
            item["provider_ids"] = sorted(set(item["provider_ids"]))
    payload = (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    # Validate outgoing bytes too. No arbitrary metadata can bypass the import boundary.
    parse_map("export.json", payload)
    return payload


def map_checksum(model):
    return hashlib.sha256(canonical_map(model)).hexdigest()
