from typing import Dict, List, Optional, Any
from backend.cluster.node_registry import NodeRegistry, NodeState


class CapabilityRoutingError(Exception):
    pass


class CapabilityRouter:

    def __init__(self, node_registry: NodeRegistry):
        self.node_registry = node_registry

    def select_best_node(
        self,
        required_capability: str,
        data_locality: str = "transferable",  # local_only, transferable, encrypted_transfer
        min_vram_mb: int = 0,
        min_cpu_cores: int = 1
    ) -> Dict[str, Any]:
        eligible_nodes = []
        all_nodes = self.node_registry.list_nodes()

        for node in all_nodes:
            # 1. State check (Must be CONNECTED or APPROVED)
            state = node.get("node_state")
            if state not in [NodeState.CONNECTED.value, NodeState.APPROVED.value]:
                continue

            # 2. Health check
            if node.get("health") != "healthy":
                continue

            # 3. Capability check
            granted_caps = node.get("granted_capabilities", node.get("capabilities", []))
            if required_capability not in granted_caps and "system.admin" not in granted_caps and "*" not in granted_caps:
                continue

            # 4. Data Locality Enforcement
            if data_locality == "local_only" and not node.get("is_local", False):
                continue

            # 5. Hardware Profile Check
            hw = node.get("hardware_profile", {})
            if hw.get("cpu_cores", 0) < min_cpu_cores:
                continue
            if hw.get("vram_mb", 0) < min_vram_mb:
                continue

            eligible_nodes.append(node)

        if not eligible_nodes:
            raise CapabilityRoutingError(
                f"No eligible node found matching capability '{required_capability}' with locality='{data_locality}'."
            )

        # Prefer local node first, then sort by highest VRAM / CPU cores
        eligible_nodes.sort(
            key=lambda n: (
                1 if n.get("is_local") else 0,
                n.get("hardware_profile", {}).get("vram_mb", 0),
                n.get("hardware_profile", {}).get("cpu_cores", 0)
            ),
            reverse=True
        )

        return eligible_nodes[0]
