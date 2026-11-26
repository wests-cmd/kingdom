"""Read-only deterministic intents and explicitly saved, project-scoped aliases.

Never interpret shell, arbitrary Python, model output, or memory as a command.
The existing authenticated request bridge remains the only execution entry.
"""
import re

COMMANDS = {
    "time": "Show the controller's current time",
    "status": "Show the runtime status",
    "priorities": "Show unfinished work in this project",
    "work": "Show recent requests in this conversation",
    "harnesses": "List configured harness names (not credentials or arguments)",
    "help": "Show available instant commands",
}
NATURAL = {
    "time": "time", "what time is it": "time", "what is the current time": "time",
    "status": "status", "system status": "status", "runtime status": "status",
    "what is the status": "status", "what is the runtime status": "status",
    "what is the system status": "status", "show my recent work": "work",
    "show configured harnesses": "harnesses",
}
ALIAS = re.compile(r"[a-z][a-z0-9_-]{0,39}")


class ShortcutStore:
    def __init__(self, database):
        self.db = database
        with self.db.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS request_shortcuts(
                project_scope TEXT NOT NULL, name TEXT NOT NULL, command TEXT NOT NULL,
                PRIMARY KEY(project_scope,name))""")
            conn.commit()

    def list(self, project):
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT name,command FROM request_shortcuts WHERE project_scope=? ORDER BY name", (project,)).fetchall()
        return [{"name": row[0], "command": row[1]} for row in rows if row[1] in COMMANDS]

    def save(self, project, name, command):
        if not ALIAS.fullmatch(name) or name in COMMANDS or command not in COMMANDS:
            raise ValueError("Use a distinct short alias for a built-in read-only command")
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute("SELECT COUNT(*) FROM request_shortcuts WHERE project_scope=?", (project,)).fetchone()[0]
            exists = conn.execute("SELECT 1 FROM request_shortcuts WHERE project_scope=? AND name=?", (project,name)).fetchone()
            if count >= 32 and not exists:
                raise ValueError("This project has reached its 32-shortcut limit")
            conn.execute("INSERT INTO request_shortcuts VALUES(?,?,?) ON CONFLICT(project_scope,name) DO UPDATE SET command=excluded.command", (project,name,command))
            conn.commit()
        return {"name": name, "command": command}

    def remove(self, project, name):
        with self.db.get_connection() as conn:
            count = conn.execute("DELETE FROM request_shortcuts WHERE project_scope=? AND name=?", (project,name)).rowcount
            conn.commit()
        return bool(count)


def resolve(prompt, project, shortcuts):
    text = prompt.strip()
    if text.startswith("/"):
        # Exact single tokens only. Unknown slash commands fail closed rather
        # than being passed to an LLM that might interpret them as actions.
        name = text[1:]
        if name in COMMANDS:
            return name
        if ALIAS.fullmatch(name):
            for item in shortcuts.list(project):
                if item["name"] == name:
                    return item["command"]
        raise ValueError("Unknown instant command; use /help")
    return NATURAL.get(text.lower().rstrip("?.!"))
