"""Capability-based permissions for Kingdom's zero-trust security model."""

from __future__ import annotations

from typing import Iterable

# Standard capability definitions
CAPABILITY_FILESYSTEM_READ = "filesystem.read"
CAPABILITY_FILESYSTEM_WRITE = "filesystem.write"
CAPABILITY_FILESYSTEM_DELETE = "filesystem.delete"
CAPABILITY_PROCESS_EXECUTE = "process.execute"
CAPABILITY_NETWORK_ACCESS = "network.access"
CAPABILITY_DOCKER_EXECUTE = "docker.execute"
CAPABILITY_MODEL_INFERENCE = "model.inference"
CAPABILITY_MEMORY_READ = "memory.read"
CAPABILITY_MEMORY_WRITE = "memory.write"
CAPABILITY_AI_MAP_READ = "ai_map.read"
CAPABILITY_AI_MAP_WRITE = "ai_map.write"
CAPABILITY_NODE_REGISTER = "node.register"
CAPABILITY_NODE_EXECUTE = "node.execute"
CAPABILITY_SYSTEM_ADMIN = "system.admin"

ALL_CAPABILITIES = {
    CAPABILITY_FILESYSTEM_READ,
    CAPABILITY_FILESYSTEM_WRITE,
    CAPABILITY_FILESYSTEM_DELETE,
    CAPABILITY_PROCESS_EXECUTE,
    CAPABILITY_NETWORK_ACCESS,
    CAPABILITY_DOCKER_EXECUTE,
    CAPABILITY_MODEL_INFERENCE,
    CAPABILITY_MEMORY_READ,
    CAPABILITY_MEMORY_WRITE,
    CAPABILITY_AI_MAP_READ,
    CAPABILITY_AI_MAP_WRITE,
    CAPABILITY_NODE_REGISTER,
    CAPABILITY_NODE_EXECUTE,
    CAPABILITY_SYSTEM_ADMIN,
}

# Default capabilities assigned to regular non-admin nodes or actors
DEFAULT_KNIGHT_CAPABILITIES = {
    CAPABILITY_MODEL_INFERENCE,
    CAPABILITY_MEMORY_READ,
    CAPABILITY_MEMORY_WRITE,
    CAPABILITY_AI_MAP_READ,
    CAPABILITY_AI_MAP_WRITE,
    CAPABILITY_NODE_EXECUTE,
}

# Privileged capabilities requiring strict policy check / human approval
PRIVILEGED_CAPABILITIES = {
    CAPABILITY_FILESYSTEM_WRITE,
    CAPABILITY_FILESYSTEM_DELETE,
    CAPABILITY_PROCESS_EXECUTE,
    CAPABILITY_DOCKER_EXECUTE,
    CAPABILITY_NETWORK_ACCESS,
    CAPABILITY_SYSTEM_ADMIN,
}


class CapabilityEvaluator:
    """Evaluates whether granted capabilities satisfy required capabilities."""

    @staticmethod
    def evaluate(granted: Iterable[str], required: str) -> bool:
        """
        Deny-by-default capability evaluation.
        Supports wildcards (e.g., 'filesystem.*' or '*') and exact matches.
        """
        if not required or not isinstance(required, str):
            return False

        granted_set = set(granted or [])

        if "*" in granted_set or "system.admin" in granted_set:
            return True

        if required in granted_set:
            return True

        # Check domain wildcard, e.g. "filesystem.*" matching "filesystem.read"
        if "." in required:
            domain = required.split(".")[0]
            if f"{domain}.*" in granted_set:
                return True

        return False
