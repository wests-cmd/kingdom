import json
import asyncio
import logging
import re
import sqlite3
import time
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from backend.integrations.discord_ai_map.adapter import DiscordAdapter, message
from backend.integrations.discord_ai_map.config import DiscordConfig

router = APIRouter()
adapter = None


class WebhookLogFilter(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r"(/webhooks/)[^\s\"?]+", r"\1[REDACTED]", record.getMessage())
        record.args = ()
        return True


def initialize(service, linker, config=None):
    global adapter
    adapter = DiscordAdapter(config or DiscordConfig.from_environment(), service, linker)
    logging.getLogger("httpx").addFilter(WebhookLogFilter())


@router.post("/discord/interactions")
async def interactions(request: Request, background: BackgroundTasks):
    if not adapter.config.enabled:
        raise HTTPException(503, "Discord integration is disabled")
    body = bytearray()
    verified = False
    try:
        async with asyncio.timeout(2):
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    raise HTTPException(413, "Interaction exceeds size limit")
    except TimeoutError as exc:
        raise HTTPException(408, "Interaction request body timed out") from exc
    try:
        adapter.verify(request.headers.get("X-Signature-Ed25519", ""),
                       request.headers.get("X-Signature-Timestamp", ""), bytes(body))
        verified = True
        interaction = json.loads(body)
        if str(interaction.get("application_id")) != adapter.config.application_id:
            raise HTTPException(403, "Discord application does not match configuration")
        interaction_id = str(interaction.get("id", ""))
        if not interaction_id.isdigit() or len(interaction_id) > 30:
            raise ValueError("Invalid interaction identity")
        # Atomic replay rejection. No tokens, signatures or raw bodies are persisted.
        with adapter.service.repository.db.get_connection() as conn:
            conn.execute("PRAGMA busy_timeout=500")
            conn.execute("DELETE FROM integration_records WHERE kind='discord_request' AND updated_at<?", (time.time() - 600,))
            conn.execute("INSERT INTO integration_records VALUES('discord_request',?,'{}',?)", (interaction_id, time.time()))
        if interaction.get("type") == 1:
            return {"type": 1}
        # Acknowledge before SQLite-heavy command work, file download or network delivery.
        background.add_task(adapter.deliver_interaction, interaction)
        return {"type": 5, "data": {"flags": 64}}
    except PermissionError:
        if not verified:
            raise HTTPException(401, "Invalid or expired Discord signature")
        return message("Link your identity and ask the Kingdom owner to review your permissions.")
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Interaction already received") from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(503, "Kingdom state is temporarily busy") from exc
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return message("Request could not be completed. Check the command, file schema and Kingdom state.")
