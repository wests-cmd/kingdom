"""
Capability Resolver Engine.
Resolves user profiles -> capabilities -> available verified API providers in a deterministic, explainable manner.
"""

from typing import Dict, Any, List, Optional
from backend.catalog.repository import catalog_repo


class CapabilityResolver:
    def __init__(self, repository=None):
        self.repo = repository or catalog_repo

    def resolve_profile_capabilities(self, user_id: str = "default_user", requested_capability: Optional[str] = None) -> Dict[str, Any]:
        """Resolves active user profile capabilities and matches available API providers."""
        active_profile = self.repo.get_active_user_profile(user_id)
        profile_details = active_profile.get("profile_details") or {}
        capabilities = profile_details.get("capabilities", [])

        if requested_capability:
            target_caps = [c for c in capabilities if c["slug"] == requested_capability or c["id"] == requested_capability]
            if not target_caps:
                # Fallback check directly in capability vocabulary
                cap = self.repo.get_capability(requested_capability)
                if cap:
                    target_caps = [cap]
        else:
            target_caps = capabilities

        resolved_capabilities = []

        for cap in target_caps:
            providers = self.repo.list_api_providers(capability_slug=cap["slug"])
            matched_providers = []

            for p in providers:
                reasons = [
                    f"Mapped to capability '{cap['name']}'",
                    "HTTPS supported" if p.get("https_supported") else "HTTP only",
                    f"Authentication: {p.get('auth_type')}",
                    f"Verification status: {p.get('verification_status')}"
                ]

                matched_providers.append({
                    "id": p["id"],
                    "slug": p["slug"],
                    "name": p["name"],
                    "description": p.get("description"),
                    "homepage_url": p.get("homepage_url"),
                    "auth_type": p.get("auth_type"),
                    "https_supported": bool(p.get("https_supported")),
                    "free_access": p.get("free_access"),
                    "verification_status": p.get("verification_status"),
                    "reasons": reasons
                })

            resolved_capabilities.append({
                "capability_id": cap["id"],
                "capability_slug": cap["slug"],
                "capability_name": cap["name"],
                "category": cap.get("category"),
                "risk_level": cap.get("risk_level"),
                "requires_auth": bool(cap.get("requires_auth")),
                "requires_approval": bool(cap.get("requires_approval")),
                "providers_count": len(matched_providers),
                "providers": matched_providers
            })

        return {
            "user_id": user_id,
            "active_profile": {
                "id": profile_details.get("id"),
                "name": profile_details.get("name"),
                "slug": profile_details.get("slug"),
                "description": profile_details.get("description")
            },
            "resolved_capabilities_count": len(resolved_capabilities),
            "capabilities": resolved_capabilities
        }


capability_resolver = CapabilityResolver()
