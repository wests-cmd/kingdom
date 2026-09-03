import time
import uuid
from typing import List, Dict, Any, Optional
from backend.skills.repository import skill_repo

DEPARTMENTS = [
    "Research",
    "Finance",
    "Data Analysis",
    "Communications",
    "Scheduling",
    "Security",
    "File Management",
    "Development",
    "Monitoring"
]

DEFAULT_BUILTIN_SKILLS = [
    {
        "id": "skill-market-research",
        "name": "Market Research",
        "description": "Analyzes market trends, news feeds, and competitor intelligence.",
        "version": "1.2.0",
        "provider": "Kingdom Core",
        "state": "active",
        "department": "Research",
        "capabilities": ["model.inference", "network.access"],
        "trust_status": "verified",
        "processes": [
            {
                "name": "Analyze Market Data",
                "required_departments": ["Data Analysis", "Research"],
                "required_tools": ["Market Data API"],
                "optional_departments": ["Finance"]
            },
            {
                "name": "Generate Trend Brief",
                "required_departments": ["Research"],
                "required_tools": ["LLM Summarizer"]
            }
        ],
        "dependencies": {
            "required_skills": ["skill-data-cleaning"],
            "required_departments": ["Research", "Data Analysis"],
            "required_tools": ["Market Data API", "LLM Summarizer"],
            "required_capabilities": ["model.inference", "network.access"]
        }
    },
    {
        "id": "skill-data-cleaning",
        "name": "Data Cleaning & Parsing",
        "description": "Standardizes raw data feeds into structured graph memory format.",
        "version": "1.0.0",
        "provider": "Kingdom Core",
        "state": "installed",
        "department": "Data Analysis",
        "capabilities": ["memory.write", "memory.read"],
        "trust_status": "verified",
        "processes": [
            {
                "name": "Parse Structured JSON/CSV",
                "required_departments": ["Data Analysis"],
                "required_tools": ["JSON Parser"]
            }
        ],
        "dependencies": {
            "required_skills": [],
            "required_departments": ["Data Analysis"],
            "required_tools": ["JSON Parser"],
            "required_capabilities": ["memory.write"]
        }
    },
    {
        "id": "skill-portfolio-analysis",
        "name": "Portfolio Analysis",
        "description": "Calculates risk exposure and yield across financial assets.",
        "version": "1.1.0",
        "provider": "Kingdom Core",
        "state": "saved",
        "department": "Finance",
        "capabilities": ["model.inference"],
        "trust_status": "verified",
        "processes": [
            {
                "name": "Calculate Asset Yield",
                "required_departments": ["Finance", "Data Analysis"],
                "required_tools": ["Yield Calculator API"]
            }
        ],
        "dependencies": {
            "required_skills": ["skill-market-research", "skill-data-cleaning"],
            "required_departments": ["Finance", "Research", "Data Analysis"],
            "required_tools": ["Yield Calculator API"],
            "required_capabilities": ["model.inference"]
        }
    },
    {
        "id": "skill-code-review",
        "name": "Automated Code Review",
        "description": "Inspects git pull requests for security vulnerabilities and code quality.",
        "version": "2.0.0",
        "provider": "Kingdom Core",
        "state": "active",
        "department": "Development",
        "capabilities": ["filesystem.read", "process.execute"],
        "trust_status": "verified",
        "processes": [
            {
                "name": "AST Vulnerability Analysis",
                "required_departments": ["Development", "Security"],
                "required_tools": ["AST Parser", "Security Scanner"]
            }
        ],
        "dependencies": {
            "required_skills": [],
            "required_departments": ["Development", "Security"],
            "required_tools": ["AST Parser", "Security Scanner"],
            "required_capabilities": ["filesystem.read"]
        }
    }
]

class SkillEngine:

    def __init__(self, repository=None):
        self.repo = repository or skill_repo
        self.init_builtin_skills()

    def init_builtin_skills(self):
        for sk in DEFAULT_BUILTIN_SKILLS:
            if not self.repo.get_skill(sk["id"]):
                self.repo.save_skill(sk)

    def list_skills(self) -> List[Dict[str, Any]]:
        return self.repo.list_skills()

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_skill(skill_id)

    def save_skill(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        sk_id = skill_data.get("id") or f"skill-{uuid.uuid4().hex[:8]}"

        skill = {
            "id": sk_id,
            "name": skill_data.get("name", "Untitled Skill"),
            "description": skill_data.get("description", ""),
            "version": skill_data.get("version", "1.0.0"),
            "provider": skill_data.get("provider", "User Saved"),
            "state": skill_data.get("state", "saved"),
            "department": skill_data.get("department", "General"),
            "processes": skill_data.get("processes", []),
            "dependencies": skill_data.get("dependencies", {}),
            "capabilities": skill_data.get("capabilities", []),
            "trust_status": skill_data.get("trust_status", "verified"),
            "created_at": skill_data.get("created_at", now),
            "updated_at": now
        }

        self.repo.save_skill(skill)
        return skill

    def _detect_circular_dependency(self, start_id: str, current_id: str, visited: set) -> bool:
        if current_id in visited:
            return True
        visited.add(current_id)

        sk = self.get_skill(current_id)
        if not sk:
            return False

        req_skills = sk.get("dependencies", {}).get("required_skills", [])
        for dep_id in req_skills:
            if dep_id == start_id or self._detect_circular_dependency(start_id, dep_id, set(visited)):
                return True
        return False

    def resolve_dependencies(self, skill_id: str, chosen_departments: Optional[List[str]] = None) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found", "readiness_status": "NOT READY"}

        deps = skill.get("dependencies", {})
        req_skills = set(deps.get("required_skills", []))
        req_depts = set(deps.get("required_departments", [skill.get("department")]))
        req_tools = set(deps.get("required_tools", []))
        req_caps = set(deps.get("required_capabilities", []))

        # Check circular dependencies
        is_circular = self._detect_circular_dependency(skill_id, skill_id, set())

        # Check availability against installed/active skills
        all_installed = {s["id"]: s for s in self.repo.list_skills() if s.get("state") in ["installed", "active"]}

        missing_skills = [sid for sid in req_skills if sid not in all_installed]
        missing_departments = []
        if chosen_departments is not None:
            missing_departments = [d for d in req_depts if d not in chosen_departments]

        # Shared dependencies calculation
        shared_dependencies = list(req_skills.intersection(set(all_installed.keys())))

        readiness = "READY"
        if is_circular:
            readiness = "CIRCULAR DEPENDENCY DETECTED"
        elif missing_skills or missing_departments:
            readiness = "PARTIALLY READY" if len(missing_skills) < len(req_skills) else "NOT READY"

        return {
            "skill_id": skill_id,
            "skill_name": skill["name"],
            "circular_dependency_detected": is_circular,
            "required_skills": list(req_skills),
            "required_departments": list(req_depts),
            "required_tools": list(req_tools),
            "required_capabilities": list(req_caps),
            "shared_dependencies": shared_dependencies,
            "missing_skills": missing_skills,
            "missing_departments": missing_departments,
            "readiness_status": readiness,
            "processes": skill.get("processes", [])
        }

    def install_skill(self, skill_id: str, chosen_departments: Optional[List[str]] = None) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        resolution = self.resolve_dependencies(skill_id, chosen_departments=chosen_departments)

        for req_sid in resolution.get("required_skills", []):
            req_sk = self.get_skill(req_sid)
            if req_sk and req_sk.get("state") == "saved":
                req_sk["state"] = "installed"
                self.repo.save_skill(req_sk)

        skill["state"] = "installed"
        self.repo.save_skill(skill)

        return {
            "skill": skill,
            "resolution": resolution
        }

    def remove_skill(self, skill_id: str) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        # Find all other remaining skills
        other_skills = [s for s in self.repo.list_skills() if s["id"] != skill_id]

        # Collect dependencies required by other remaining installed/active skills
        deps_needed_by_others = set()
        for s in other_skills:
            if s.get("state") in ["installed", "active"]:
                for req_id in s.get("dependencies", {}).get("required_skills", []):
                    deps_needed_by_others.add(req_id)

        # Delete skill
        self.repo.delete_skill(skill_id)

        # Ensure dependencies still needed by other skills remain intact
        # (This guarantees shared dependencies like Dep X are retained)
        return {
            "removed_skill_id": skill_id,
            "retained_shared_dependencies": list(deps_needed_by_others)
        }

    def activate_skill(self, skill_id: str) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        skill["state"] = "active"
        self.repo.save_skill(skill)
        return skill

    def deactivate_skill(self, skill_id: str) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        skill["state"] = "installed"
        self.repo.save_skill(skill)
        return skill

    def create_bundle(self, name: str, description: str, skill_ids: List[str]) -> Dict[str, Any]:
        now = time.time()
        b_id = f"bundle-{uuid.uuid4().hex[:8]}"

        all_req_skills = set()
        all_req_depts = set()
        all_req_tools = set()

        for sid in skill_ids:
            sk = self.get_skill(sid)
            if sk:
                deps = sk.get("dependencies", {})
                all_req_skills.update(deps.get("required_skills", []))
                all_req_depts.update(deps.get("required_departments", []))
                all_req_tools.update(deps.get("required_tools", []))

        bundle = {
            "id": b_id,
            "name": name,
            "description": description,
            "skill_ids": skill_ids,
            "deduplicated_dependencies": {
                "skills_count": len(skill_ids),
                "departments": list(all_req_depts),
                "required_skills": list(all_req_skills),
                "tools": list(all_req_tools)
            },
            "created_at": now,
            "updated_at": now
        }

        self.repo.save_bundle(bundle)
        return bundle

    def list_bundles(self) -> List[Dict[str, Any]]:
        return self.repo.list_bundles()

# Global skill engine instance
skill_engine = SkillEngine()
