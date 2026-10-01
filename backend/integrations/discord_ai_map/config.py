"""Configuration is opt-in. Never print environment credentials."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscordConfig:
    enabled: bool
    application_id: str = ""
    public_key: str = ""
    bot_token: str = field(default="", repr=False)
    guild_id: str = ""

    @classmethod
    def from_environment(cls):
        config = cls(os.getenv("KINGDOM_DISCORD_ENABLED", "false").lower() == "true",
                     os.getenv("KINGDOM_DISCORD_APPLICATION_ID", ""), os.getenv("KINGDOM_DISCORD_PUBLIC_KEY", ""),
                     os.getenv("KINGDOM_DISCORD_BOT_TOKEN", ""), os.getenv("KINGDOM_DISCORD_GUILD_ID", ""))
        if config.enabled:
            try:
                valid = config.application_id.isdigit() and len(config.application_id) <= 30 and len(bytes.fromhex(config.public_key)) == 32 and bool(config.bot_token) and (not config.guild_id or config.guild_id.isdigit())
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Discord enabled but required application configuration is incomplete")
        return config
