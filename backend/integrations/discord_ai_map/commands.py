"""Explicit command registration; importing Kingdom never registers or sends messages."""
import argparse
import httpx
from backend.integrations.discord_ai_map.config import DiscordConfig


def command_definitions():
    commands = [{"name": name, "description": description, "type": 1} for name, description in (
        ("kingdom", "Request an explicit Kingdom identity link"), ("status", "View Kingdom runtime status"),
        ("knights", "View installed Kingdom workers"), ("profiles", "View your Kingdom profile preferences"),
        ("skills", "View saved Kingdom skill counts"), ("apis", "View reviewed provider-test adapters"),
        ("tasks", "View your provider-test tasks"), ("help", "Explain Kingdom commands and permissions"))]
    commands.append({"name": "skillmap", "description": "Import, export or test portable preferences", "type": 1,
        "options": [{"name": "import", "description": "Preview an attached skill map", "type": 1,
                     "options": [{"name": "file", "description": "JSON or safe YAML skill map", "type": 11, "required": True}]},
                    *[{"name": action, "description": description, "type": 1,
                       "options": [{"name": "map_id", "description": "Saved map identifier", "type": 3, "required": True,
                                    "max_length": 64}]} for action, description in
                      (("export", "Export canonical JSON with its checksum"), ("test", "Queue governed read-only provider tests"))]]})
    for command in commands:
        if command["name"] == "profiles":
            command["options"] = [{"name": key, "description": description, "type": 3, "max_length": 64} for key, description in
                                  (("profile_id", "Preferred installed profile; also supply map_id"), ("map_id", "Your saved map; also supply profile_id"))]
        if command["name"] == "apis":
            command["options"] = [{"name": "provider_id", "description": "Reviewed provider to configure; also supply enabled", "type": 3, "max_length": 64},
                                  {"name": "enabled", "description": "Enable or disable its read-only test", "type": 5}]
    return commands


def register_commands(config):
    if not config.enabled or not config.bot_token:
        raise ValueError("Discord registration requires a complete enabled configuration")
    path = f"https://discord.com/api/v10/applications/{config.application_id}"
    if config.guild_id:
        path += f"/guilds/{config.guild_id}"
    path += "/commands"
    # Upsert by command name. Preserve unrelated application commands.
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        for command in command_definitions():
            response = client.post(path, headers={"Authorization": "Bot " + config.bot_token}, json=command)
            if response.status_code not in (200, 201):
                raise RuntimeError("Discord command registration was rejected; verify configuration and permissions")
    return {"registered": len(command_definitions())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register Kingdom Discord application commands")
    parser.add_argument("--register", action="store_true", required=True)
    parser.parse_args()
    try:
        result = register_commands(DiscordConfig.from_environment())
        print(f"Registered {result['registered']} Kingdom commands.")
    except (ValueError, RuntimeError, httpx.HTTPError):
        raise SystemExit("Discord registration failed. Check the enabled application configuration; credentials are never printed.")
