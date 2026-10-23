"""Typed observation only; running and startup evidence are separate."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ServiceSummary(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    state: Literal['running', 'stopped', 'unknown']
    startup: Literal['enabled', 'disabled', 'manual', 'unknown'] = 'unknown'


class ServiceReport(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True, allow_inf_nan=False)
    state: Literal['observed', 'unsupported', 'unavailable']
    scope: Literal['user_services', 'windows_services', 'container', 'unknown'] = 'unknown'
    running_state: Literal['observed', 'unsupported', 'unavailable', 'unknown'] = 'unknown'
    startup_state: Literal['observed', 'unsupported', 'unavailable', 'unknown'] = 'unknown'
    services: list[ServiceSummary] = Field(max_length=128)
    observed_at: float | None = Field(default=None, ge=0)
    truncated: bool = False


def validate_services(value):
    report = ServiceReport.model_validate(value).model_dump()
    if report['state'] != 'observed' and report['services']:
        raise ValueError('Unavailable services cannot contain current rows')
    if report['startup_state'] != 'observed' and any(row['startup'] != 'unknown' for row in report['services']):
        raise ValueError('Startup evidence unavailable')
    seen = set()
    for row in report['services']:
        if row['id'] in seen or any(any(ord(char) < 32 for char in row[field]) for field in ('id', 'name')):
            raise ValueError('Invalid or duplicate service label')
        seen.add(row['id'])
        if row['state'] != 'unknown' and report['running_state'] not in {'observed', 'unknown'}:
            raise ValueError('Running evidence unavailable')
    return report
