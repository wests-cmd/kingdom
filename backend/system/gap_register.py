"""Persistent gap register tracking system capabilities, missing work, and live test evidence."""
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


INITIAL_CAPABILITIES = [
    {
        "id": "autonomous-planning",
        "capability": "Autonomous planning",
        "existing_implementation": "Chat proposals, ChatGPT plan integration, and Work programme runners",
        "missing_work": "End-to-end goal decomposition with automatic strategy refinement without manual approvals",
        "test_evidence": "tests/test_chatgpt_plan.py, tests/test_work_programme_runner.py",
        "priority": "P0",
        "status": "partial"
    },
    {
        "id": "multi-model-routing",
        "capability": "Multi-model routing",
        "existing_implementation": "Model router, Hybrid router, Ollama chat adapter, and Model lab",
        "missing_work": "Dynamic cost-aware and latency-benchmarked routing across cloud and local providers",
        "test_evidence": "tests/test_model_lab.py, tests/unit/test_ollama_chat.py",
        "priority": "P0",
        "status": "partial"
    },
    {
        "id": "acp-tool-adapters",
        "capability": "ACP/tool adapters",
        "existing_implementation": "Tool workshop, CLI Harness profiles, and MCP server adapter",
        "missing_work": "Agent Client Protocol standard compliance for Codex, Claude Code, and Gemini CLI",
        "test_evidence": "tests/test_tool_workshop.py, tests/test_harness_connections.py",
        "priority": "P0",
        "status": "partial"
    },
    {
        "id": "autonomous-coding",
        "capability": "Autonomous coding",
        "existing_implementation": "Coder knight, Jules backlog runner, Workshop adapter, and Self-build guard",
        "missing_work": "Closed-loop git worktree branch management, compile-test-patch cycles with self-modification fences",
        "test_evidence": "tests/test_work_backlog.py, tests/test_jules_adapter.py, tests/test_self_build_guard.py",
        "priority": "P0",
        "status": "verified"
    },
    {
        "id": "independent-verification",
        "capability": "Independent verification",
        "existing_implementation": "Verification engine, Jules independent review, boss review runner, and Self-build guard promotion gates",
        "missing_work": "Cross-agent independent verification isolating creator tokens from verifier assertions",
        "test_evidence": "tests/test_jules_independent_gate.py, tests/test_programme_acceptance_fences.py, tests/test_self_build_guard.py",
        "priority": "P0",
        "status": "verified"
    },
    {
        "id": "self-repair",
        "capability": "Self-repair",
        "existing_implementation": "Rollback engine, retry engine, and safe mode recovery",
        "missing_work": "Automated code patch synthesis upon test failures with bounded attempts",
        "test_evidence": "tests/unit/test_operational_recovery.py, tests/test_system_updater_and_migrations.py",
        "priority": "P0",
        "status": "partial"
    },
    {
        "id": "persistent-memory",
        "capability": "Persistent memory",
        "existing_implementation": "SQLite DB repository, Tiered vault, Portable vault, and Vector index",
        "missing_work": "Long-term experiential learning cross-indexed with task outcomes and failure signatures",
        "test_evidence": "tests/unit/test_memory.py, tests/unit/test_portable_vault.py",
        "priority": "P0",
        "status": "verified"
    },
    {
        "id": "recovery-after-restart",
        "capability": "Recovery after restart",
        "existing_implementation": "Runtime engine task reconciliation, scheduled runner, and recovery router",
        "missing_work": "Durable execution graphs with idempotent state resumption without re-running completed side effects",
        "test_evidence": "tests/unit/test_durable_workflow_checkpoints.py, tests/test_runtime_core.py",
        "priority": "P0",
        "status": "verified"
    },
    {
        "id": "swarm-administration",
        "capability": "Swarm administration",
        "existing_implementation": "Mesh API, federation API, command hierarchy, and node registry",
        "missing_work": "Fine-grained permission tiers (Observe, Assist, Develop, Admin, Experimental) and fleet bulk updates",
        "test_evidence": "tests/test_swarm_authority.py, tests/unit/test_cluster_federation.py",
        "priority": "P0",
        "status": "partial"
    },
    {
        "id": "security-isolation",
        "capability": "Security isolation",
        "existing_implementation": "Zero trust engine, prompt firewall, credential broker, and audit logger",
        "missing_work": "Host-level sandbox enforcement for destructive tasks and non-root execution boundaries",
        "test_evidence": "tests/test_security.py, tests/unit/test_credential_broker.py",
        "priority": "P0",
        "status": "verified"
    },
    {
        "id": "voice-and-vision",
        "capability": "Voice and vision",
        "existing_implementation": "Desktop observation, screenshot capture, and audio preferences",
        "missing_work": "Real-time bidirectional voice streaming and multimodal vision prompt analysis",
        "test_evidence": "tests/test_desktop_observation.py",
        "priority": "P1",
        "status": "partial"
    },
    {
        "id": "automatic-releases",
        "capability": "Automatic releases",
        "existing_implementation": "CI matrix workflows, release manifest validator, and UI components packager",
        "missing_work": "Automated regression benchmark gate triggering signed tag creation and release notes generation",
        "test_evidence": "tests/test_release_artifact_integrity.py, tests/test_version_preparation.py",
        "priority": "P1",
        "status": "verified"
    },
    {
        "id": "resource-optimization",
        "capability": "Resource optimization",
        "existing_implementation": "Lightweight swarm mode, local load monitor, and sliding window router",
        "missing_work": "Strict 4GB RAM / dual-core runtime throttling and intelligent Knight unloading",
        "test_evidence": "tests/test_cluster_capacity.py, tests/unit/test_learning_collector_limits.py",
        "priority": "P1",
        "status": "partial"
    },
    {
        "id": "beginner-installation",
        "capability": "Beginner installation",
        "existing_implementation": "First-run wizard, install profiles, and desktop launcher scripts",
        "missing_work": "One-click bundled runtime installer with zero CLI prerequisites across platforms",
        "test_evidence": "tests/unit/test_install_profile_registry.py, tests/test_release_installation_contract.py",
        "priority": "P1",
        "status": "verified"
    }
]


class GapRegisterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    capability: str = Field(min_length=1, max_length=200)
    existing_implementation: str = Field(min_length=1, max_length=2000)
    missing_work: str = Field(min_length=1, max_length=2000)
    test_evidence: str = Field(min_length=1, max_length=2000)
    priority: str = Field(pattern=r"^P[0-3]$")
    status: str = Field(pattern=r"^(missing|partial|verified|blocked)$")
    updated_at: float = Field(default_factory=time.time)


class GapRegister:
    def __init__(self, database):
        self.db = database
        self._init_db()

    def _init_db(self):
        with self.db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gap_register (
                    id TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    existing_implementation TEXT NOT NULL,
                    missing_work TEXT NOT NULL,
                    test_evidence TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            # Seed initial entries if table is empty
            count = conn.execute("SELECT COUNT(*) FROM gap_register").fetchone()[0]
            if count == 0:
                now = time.time()
                for item in INITIAL_CAPABILITIES:
                    conn.execute(
                        """
                        INSERT INTO gap_register (id, capability, existing_implementation, missing_work, test_evidence, priority, status, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["id"],
                            item["capability"],
                            item["existing_implementation"],
                            item["missing_work"],
                            item["test_evidence"],
                            item["priority"],
                            item["status"],
                            now
                        )
                    )
            conn.commit()

    def list(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, capability, existing_implementation, missing_work, test_evidence, priority, status, updated_at
                FROM gap_register
                ORDER BY priority ASC, id ASC
                """
            ).fetchall()
        return [
            {
                "id": r[0],
                "capability": r[1],
                "existing_implementation": r[2],
                "missing_work": r[3],
                "test_evidence": r[4],
                "priority": r[5],
                "status": r[6],
                "updated_at": r[7]
            }
            for r in rows
        ]

    def get(self, ident: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            r = conn.execute(
                """
                SELECT id, capability, existing_implementation, missing_work, test_evidence, priority, status, updated_at
                FROM gap_register WHERE id = ?
                """,
                (ident,)
            ).fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "capability": r[1],
            "existing_implementation": r[2],
            "missing_work": r[3],
            "test_evidence": r[4],
            "priority": r[5],
            "status": r[6],
            "updated_at": r[7]
        }

    def update_evidence(self, ident: str, test_evidence: str, status: Optional[str] = None) -> Dict[str, Any]:
        existing = self.get(ident)
        if not existing:
            raise KeyError(f"Gap item '{ident}' not found")
        new_status = status or existing["status"]
        now = time.time()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE gap_register
                SET test_evidence = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (test_evidence, new_status, now, ident)
            )
            conn.commit()
        return self.get(ident)
