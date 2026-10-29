"""Typed team-message data and bounded resource settings; no authority grants."""
import hashlib
import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Identifier = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,100}$', strict=True)]
MessageKind = Literal['progress', 'result', 'summary', 'stop', 'revocation', 'recovery']
CONTROL_KINDS = frozenset({'stop', 'revocation', 'recovery'})


def utc_seconds(value):
    """Finite epoch seconds through UTC year9999; booleans are not clocks."""
    if type(value) not in (int, float) or not 0 <= value <= 253402300799 or not math.isfinite(value):
        raise ValueError('A finite supported UTC timestamp is required')
    return value


class ControlPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class StopPayload(ControlPayload):
    reason: str = Field(min_length=1, max_length=200)


class RevocationPayload(ControlPayload):
    node_id: Identifier
    revision: int = Field(ge=1, le=2**63 - 1)


class RecoveryPayload(ControlPayload):
    operation_id: Identifier
    state: Literal['query', 'not_sent', 'received']


CONTROL_PAYLOADS = {'stop': StopPayload, 'revocation': RevocationPayload, 'recovery': RecoveryPayload}


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _payload(value):
    remaining = [512]

    def visit(item, depth=0):
        remaining[0] -= 1
        if depth > 8 or remaining[0] < 0:
            raise ValueError('Payload nesting or item limit exceeded')
        if item is None or type(item) is bool:
            return
        if type(item) is int and item.bit_length() <= 64:
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is str and len(item) <= 16384:
            return
        if type(item) is list and len(item) <= 512:
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict and len(item) <= 512:
            for key, child in item.items():
                if type(key) is not str or len(key) > 128:
                    raise ValueError('Payload keys must be bounded strings')
                visit(child, depth + 1)
            return
        raise ValueError('Payload must contain bounded finite JSON values')

    if type(value) is not dict:
        raise ValueError('Payload must be a JSON object')
    visit(value)
    encoded = _json_bytes(value)
    if len(encoded) > 16384:
        raise ValueError('Small-message payload exceeds 16 KiB; use an artifact reference')
    # Detach caller-owned dictionaries/lists. Canonicalization revalidates again
    # because frozen Pydantic models do not freeze nested mutable values.
    return json.loads(encoded)


class TeamPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, validate_default=True,
                              revalidate_instances='always')

    wifi_routine_bytes: int = Field(default=10 * 1024 * 1024, ge=0, le=1024**3)
    wifi_control_bytes: int = Field(default=64 * 1024, ge=1, le=1024**2)
    window_seconds: int = Field(default=60, ge=1, le=3600)
    routine_entries: int = Field(default=1024, ge=1, le=10000)
    routine_bytes: int = Field(default=4 * 1024 * 1024, ge=1, le=64 * 1024 * 1024)
    control_entries: int = Field(default=32, ge=1, le=1024)
    control_bytes: int = Field(default=64 * 1024, ge=1, le=1024**2)
    receipt_entries: int = Field(default=10000, ge=1, le=100000)


class TeamMessage(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, revalidate_instances='always')

    version: Literal['kingdom.team-message.v1'] = 'kingdom.team-message.v1'
    message_id: Identifier
    task_id: Identifier
    sender_id: Identifier
    recipient_id: Identifier
    group_id: Identifier | None = None
    group_revision: int | None = Field(default=None, ge=0, le=2**63 - 1)
    policy_revision: int = Field(ge=1, le=2**63 - 1)
    created_at: float
    expires_at: float
    kind: MessageKind
    payload: dict[str, Any]

    @field_validator('created_at', 'expires_at', mode='before')
    @classmethod
    def validate_timestamp(cls, value):
        return utc_seconds(value)

    @field_validator('payload', mode='before')
    @classmethod
    def validate_payload(cls, value):
        return _payload(value)

    @model_validator(mode='after')
    def validate_control(self):
        if not 0 < self.expires_at - self.created_at <= 86400:
            raise ValueError('Message lifetime must be positive and no longer than 24 hours')
        if (self.group_id is None) != (self.group_revision is None):
            raise ValueError('Group delivery needs both group identity and revision')
        if self.kind in CONTROL_PAYLOADS:
            CONTROL_PAYLOADS[self.kind].model_validate(self.payload)
        return self

    def assert_current(self, now):
        """A new delivery is permitted only during its original fixed lifetime.

        This validates freshness only, never authority. Historical receipts and
        acknowledgements do not use it: expiry cannot erase delivery evidence.
        """
        validated = TeamMessage.model_validate(self.model_dump(mode='python', warnings=False))
        if not validated.created_at <= utc_seconds(now) < validated.expires_at:
            raise ValueError('Message is expired or not yet valid')
        return self

    def canonical_bytes(self):
        validated = TeamMessage.model_validate(self.model_dump(mode='python', warnings=False))
        return _json_bytes(validated.model_dump(mode='python'))

    def digest(self):
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
