"""
Catalog Synchronization Service.
Executes idempotent, non-blocking synchronization from external API sources into Kingdom's local catalog DB.
"""

import logging
import time
from typing import Dict, Any, List
from backend.catalog.repository import catalog_repo
from backend.catalog.sources.public_apis import PublicApisSourceAdapter

logger = logging.getLogger(__name__)

CATEGORY_CAPABILITY_MAP = {
    "news": ["news_search", "web_search"],
    "finance": ["financial_data", "market_research"],
    "financial": ["financial_data", "market_research"],
    "shopping": ["product_search", "product_research", "price_comparison"],
    "e-commerce": ["product_search", "product_research", "price_comparison"],
    "weather": ["weather_lookup"],
    "geocoding": ["geolocation"],
    "maps": ["geolocation"],
    "transportation": ["travel_information"],
    "travel": ["travel_information"],
    "science": ["science_data", "research"],
    "books": ["book_search"],
    "education": ["book_search", "research"],
    "development": ["code_analysis"],
    "programming": ["code_analysis"],
    "text analysis": ["text_analysis"],
    "translation": ["translation"],
    "community": ["community_moderation"],
    "social": ["community_moderation"]
}


class CatalogSyncService:
    def __init__(self, repository=None, adapter=None):
        self.repo = repository or catalog_repo
        self.adapter = adapter or PublicApisSourceAdapter()

    def sync_public_apis(self) -> Dict[str, Any]:
        """Executes idempotent synchronization from public_apis source."""
        sync_id = self.repo.create_sync_record("public_apis")
        entries = self.adapter.fetch_entries()

        if not entries:
            self.repo.update_sync_record(
                sync_id,
                status="completed",
                seen=0,
                added=0,
                updated=0,
                disabled=0,
                errors="No entries retrieved or source offline"
            )
            return {
                "sync_id": sync_id,
                "status": "completed",
                "entries_seen": 0,
                "entries_added": 0,
                "entries_updated": 0,
                "message": "Sync completed with 0 entries (source offline or disabled)."
            }

        added = 0
        updated = 0
        errors_count = 0

        for entry in entries:
            try:
                provider_slug = entry["slug"]
                existing = self.repo.get_api_provider(provider_slug)

                provider = self.repo.upsert_api_provider(entry)
                if existing:
                    updated += 1
                else:
                    added += 1

                # Link provider to capabilities based on category
                cat_lower = str(entry.get("category", "")).lower()
                target_capabilities = ["web_search"]  # default fallback
                for key, caps in CATEGORY_CAPABILITY_MAP.items():
                    if key in cat_lower:
                        target_capabilities.extend(caps)

                for cap_slug in set(target_capabilities):
                    cap = self.repo.get_capability(cap_slug)
                    if cap:
                        self.repo.link_api_capability(provider["id"], cap["id"])

            except Exception as e:
                logger.error(f"[Catalog Sync] Failed to process entry '{entry.get('name')}': {e}")
                errors_count += 1

        status_res = "completed" if errors_count == 0 else "degraded"
        err_msg = f"{errors_count} entries failed processing" if errors_count > 0 else None

        self.repo.update_sync_record(
            sync_id,
            status=status_res,
            seen=len(entries),
            added=added,
            updated=updated,
            disabled=0,
            errors=err_msg
        )

        return {
            "sync_id": sync_id,
            "status": status_res,
            "entries_seen": len(entries),
            "entries_added": added,
            "entries_updated": updated,
            "errors_count": errors_count
        }


catalog_sync_service = CatalogSyncService()
