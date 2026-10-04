"""Owner presentation preferences, stored separately from all authority settings."""
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from backend.security.http_auth import require_owner
from backend.storage.integration_repository import IntegrationRepository
from backend.events.event_bus import event_bus


class AppearancePreferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['dark', 'light', 'system'] = 'dark'
    palette: Literal['royal', 'ocean', 'jade', 'ember', 'gold'] = 'royal'
    accent: str = Field(default='#b69aff', pattern=r'^#[0-9a-fA-F]{6}$', max_length=7)
    density: Literal['comfortable', 'compact'] = 'comfortable'
    scale: Literal[90, 100, 110, 125, 150, 175, 200] = 100
    motion: Literal['system', 'reduced'] = 'system'
    atmosphere: Literal[0, 5, 10, 15, 20] = 10
    contrast: Literal['standard', 'high'] = 'standard'
    targets: Literal['standard', 'large'] = 'standard'
    focus: Literal['standard', 'strong'] = 'standard'
    pointer: Literal['standard', 'large'] = 'standard'
    reading: Literal['standard', 'spacious'] = 'standard'
    distraction: Literal['standard', 'quiet'] = 'standard'


class SavedPreferences(BaseModel):
    preferences: AppearancePreferences | None


router = APIRouter(dependencies=[Depends(require_owner)])
repository = IntegrationRepository()


@router.get('/preferences/accessibility', response_model=SavedPreferences)
def get_preferences():
    return {'preferences': repository.get('presentation_preferences', 'owner')}


@router.put('/preferences/accessibility', response_model=SavedPreferences)
def save_preferences(preferences: AppearancePreferences):
    value = preferences.model_dump()
    repository.put('presentation_preferences', 'owner', value)
    event_bus.publish('preferences.accessibility_saved', {'actor': 'owner'})
    return {'preferences': value}
