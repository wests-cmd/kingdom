import re
from typing import Any, Dict, List, Set, Tuple, Optional
from backend.skills.models import Skill, SkillLifecycleState


class DependencyResolutionError(Exception):
    pass


class CircularDependencyError(DependencyResolutionError):
    pass


class VersionConflictError(DependencyResolutionError):
    pass


class MissingDependencyError(DependencyResolutionError):
    pass


def parse_version(v_str: str) -> Tuple[int, ...]:
    clean = re.sub(r'[^0-9.]', '', v_str)
    parts = [int(p) for p in clean.split('.') if p.isdigit()]
    return tuple(parts) if parts else (0,)


def match_constraint(version: str, constraint: str) -> bool:
    if not constraint or constraint == "*":
        return True

    v_num = parse_version(version)

    m = re.match(r'^(>=|<=|>|<|==)?\s*([0-9.]+)', constraint.strip())
    if not m:
        return True

    op, req_v_str = m.groups()
    req_num = parse_version(req_v_str)

    if op == ">=":
        return v_num >= req_num
    elif op == ">":
        return v_num > req_num
    elif op == "<=":
        return v_num <= req_num
    elif op == "<":
        return v_num < req_num
    elif op == "==":
        return v_num == req_num
    else:
        # Default exact match when no operator provided
        return v_num == req_num


class SkillDependencyEngine:

    def __init__(self, available_skills: Optional[List[Skill]] = None):
        self.available_skills: Dict[str, List[Skill]] = {}
        if available_skills:
            for s in available_skills:
                self.register_skill(s)

    def register_skill(self, skill: Skill):
        if skill.name not in self.available_skills:
            self.available_skills[skill.name] = []
        self.available_skills[skill.name] = [
            s for s in self.available_skills[skill.name] if s.version != skill.version
        ]
        self.available_skills[skill.name].append(skill)

    def detect_cycles(self, target_skills: List[Skill]) -> None:
        visited = set()
        rec_stack = set()

        def dfs(skill_name: str, path: List[str]):
            visited.add(skill_name)
            rec_stack.add(skill_name)

            skills = self.available_skills.get(skill_name, [])
            if skills:
                s = skills[0]
                for req in s.dependencies.required_skills:
                    dep_name = req.name
                    if dep_name in rec_stack:
                        cycle_path = " -> ".join(path + [dep_name])
                        raise CircularDependencyError(f"Circular dependency detected: {cycle_path}")
                    if dep_name not in visited:
                        dfs(dep_name, path + [dep_name])

            rec_stack.remove(skill_name)

        for skill in target_skills:
            if skill.name not in visited:
                dfs(skill.name, [skill.name])

    def resolve(self, requested_skills: List[Skill]) -> Dict[str, Skill]:
        self.detect_cycles(requested_skills)

        resolved: Dict[str, Skill] = {}
        constraints: Dict[str, List[Tuple[str, str]]] = {}

        queue: List[Tuple[Skill, Optional[str]]] = [(s, None) for s in requested_skills]

        while queue:
            current_skill, req_by = queue.pop(0)

            if current_skill.name in resolved:
                existing = resolved[current_skill.name]
                if existing.version != current_skill.version:
                    pass
                continue

            if current_skill.name in constraints:
                for constr, by in constraints[current_skill.name]:
                    if not match_constraint(current_skill.version, constr):
                        raise VersionConflictError(
                            f"Version conflict for '{current_skill.name}': version {current_skill.version} "
                            f"does not satisfy constraint '{constr}' required by '{by}'"
                        )

            resolved[current_skill.name] = current_skill

            for req in current_skill.dependencies.required_skills:
                dep_name = req.name
                constr = req.version_constraint

                if dep_name not in constraints:
                    constraints[dep_name] = []
                constraints[dep_name].append((constr, current_skill.name))

                if dep_name in resolved:
                    res_skill = resolved[dep_name]
                    if not match_constraint(res_skill.version, constr):
                        raise VersionConflictError(
                            f"Version conflict for '{dep_name}': resolved version {res_skill.version} "
                            f"does not satisfy constraint '{constr}' required by '{current_skill.name}'"
                        )
                else:
                    candidates = self.available_skills.get(dep_name, [])
                    matching = [c for c in candidates if match_constraint(c.version, constr)]
                    if not matching:
                        raise MissingDependencyError(
                            f"Missing dependency '{dep_name}' with constraint '{constr}' required by '{current_skill.name}'"
                        )
                    matching.sort(key=lambda s: parse_version(s.version), reverse=True)
                    best_candidate = matching[0]
                    queue.append((best_candidate, current_skill.name))

        return resolved

    def generate_lock_manifest(self, resolved: Dict[str, Skill]) -> Dict[str, Any]:
        manifest = {
            "version": "1.0",
            "skills": {}
        }
        for name, skill in sorted(resolved.items()):
            manifest["skills"][name] = {
                "id": skill.id,
                "version": skill.version,
                "checksum": skill.checksum,
                "dependencies": [req.model_dump() for req in skill.dependencies.required_skills]
            }
        return manifest
