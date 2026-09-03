from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPServer:

    def __init__(self, engine: Any):
        self.engine = engine

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "submit_task",
                "description": "Submit a task payload to Kingdom swarm engine",
                "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}
            },
            {
                "name": "discover_skills",
                "description": "List available skills and their readiness",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "check_readiness",
                "description": "Check if a skill has all required tools/capabilities",
                "parameters": {"type": "object", "properties": {"skill_id": {"type": "string"}}, "required": ["skill_id"]}
            },
            {
                "name": "record_memory",
                "description": "Record memory entry into Kingdom persistent graph",
                "parameters": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}
            }
        ]

    def call_tool(self, tool_call: MCPToolCall) -> Dict[str, Any]:
        name = tool_call.name
        args = tool_call.arguments

        if name == "submit_task":
            prompt = args.get("prompt", "")
            return self.engine.submit_task(prompt)
        elif name == "discover_skills":
            skills = getattr(self.engine, "skills_manager", None)
            if skills:
                return {"skills": [s.model_dump() for s in skills.skills.values()]}
            return {"skills": []}
        elif name == "check_readiness":
            skill_id = args.get("skill_id")
            skills = getattr(self.engine, "skills_manager", None)
            if skills:
                skill = skills.skills.get(skill_id)
                if skill:
                    return skills.skill_map.check_readiness(
                        skill, skills.available_tools, skills.available_capabilities, skills.available_models, skills.granted_permissions
                    )
            return {"status": "UNKNOWN", "error": "Skill or skill manager not found"}
        elif name == "record_memory":
            content = args.get("content", "")
            return self.engine.memory.add(content)
        else:
            raise ValueError(f"Unknown MCP tool: '{name}'")
