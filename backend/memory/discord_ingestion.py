"""Parse explicit Discord message exports; no credentials, fetching or auto-ingest."""
import json
from pydantic import Field
from backend.skills.portable import StrictModel, _no_duplicates
from backend.memory.embedding_service import EmbeddingKnowledge


class ExportMessage(StrictModel):
    id: str = Field(pattern=r'^\d{1,24}$')
    channel_id: str = Field(pattern=r'^\d{1,24}$')
    author_id: str = Field(pattern=r'^\d{1,24}$')
    timestamp: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=32000)


class DiscordExport(StrictModel):
    messages: list[ExportMessage] = Field(min_length=1, max_length=100)


def parse_discord_export(payload: bytes, allowed_channel_ids: set[str], scope: str):
    """Return bounded source documents; caller explicitly confirms/embeds each."""
    EmbeddingKnowledge.scope(scope)
    if not payload or len(payload) > 262144:
        raise ValueError('Discord export must contain 1 to 262144 bytes')
    if not allowed_channel_ids or any(not isinstance(ident, str) or not ident.isascii() or not ident.isdigit() or len(ident) > 24 for ident in allowed_channel_ids):
        raise ValueError('Configure allowed Discord channel identifiers')
    try:
        data = DiscordExport.model_validate(json.loads(payload.decode('utf-8'), object_pairs_hook=_no_duplicates))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Invalid Discord message export') from error
    seen = set()
    documents = []
    for message in data.messages:
        if message.channel_id not in allowed_channel_ids:
            raise PermissionError('Discord export includes a channel outside the allowed set')
        key = (message.channel_id, message.id)
        if key in seen:
            raise ValueError('Duplicate Discord message')
        if '\x00' in message.content or not message.content.strip():
            raise ValueError('Discord content must be nonempty text')
        seen.add(key)
        documents.append({'scope': scope, 'source': f'discord:channel:{message.channel_id}:message:{message.id}',
            'text': message.content, 'provenance': {'kind':'discord-export', 'message_id':message.id,
                'channel_id':message.channel_id, 'author_id':message.author_id,
                'timestamp':message.timestamp, 'publisher_verified':False}, 'trust':'untrusted'})
    return documents
