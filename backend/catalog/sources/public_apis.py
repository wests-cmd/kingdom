"""
Public APIs Catalog Source Adapter.
Fetches external API entries from publicapis.org or configured catalog endpoints.
Isolated, read-only, non-authoritative adapter with error boundary handling.
"""

import os
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_APIS_URL = os.getenv("KINGDOM_API_CATALOG_PUBLIC_APIS_URL", "https://api.publicapis.org")
PUBLIC_APIS_ENABLED = os.getenv("KINGDOM_API_CATALOG_PUBLIC_APIS_ENABLED", "true").lower() in ("true", "1", "yes")


def normalize_auth(auth_raw: Any) -> str:
    if not auth_raw or auth_raw is None:
        return "none"
    val = str(auth_raw).strip().lower()
    if val in ("", "none", "null"):
        return "none"
    if "key" in val:
        return "api_key"
    if "oauth" in val:
        return "oauth"
    if "user-agent" in val or "useragent" in val:
        return "user_agent"
    return "unknown"


def normalize_free_access(auth_type: str, https_supported: bool) -> str:
    if auth_type == "none":
        return "free" if https_supported else "no_auth"
    if auth_type in ("api_key", "oauth"):
        return "credentials_required"
    return "unknown"


def normalize_cors(cors_raw: Any) -> str:
    if not cors_raw:
        return "unknown"
    val = str(cors_raw).strip().lower()
    if val in ("yes", "true", "1"):
        return "yes"
    if val in ("no", "false", "0"):
        return "no"
    return "unknown"


class PublicApisSourceAdapter:
    def __init__(self, base_url: str = DEFAULT_PUBLIC_APIS_URL, enabled: bool = PUBLIC_APIS_ENABLED):
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled

    def fetch_entries(self) -> List[Dict[str, Any]]:
        """Fetches and normalizes entries from Public APIs endpoint."""
        if not self.enabled:
            logger.info("[Public APIs Adapter] Source is disabled via configuration.")
            return []

        url = f"{self.base_url}/entries"
        normalized_records = []

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(f"[Public APIs Adapter] HTTP {response.status_code} from {url}")
                    return []

                data = response.json()
                entries = data.get("entries", []) if isinstance(data, dict) else []

                for entry in entries:
                    if not isinstance(entry, dict) or not entry.get("API"):
                        continue

                    name = str(entry.get("API", "")).strip()
                    desc = str(entry.get("Description", "")).strip()
                    category = str(entry.get("Category", "General")).strip()
                    link = str(entry.get("Link", "")).strip()
                    https_supported = bool(entry.get("HTTPS", True))
                    cors_raw = entry.get("Cors", "unknown")
                    auth_raw = entry.get("Auth", "")

                    auth_type = normalize_auth(auth_raw)
                    cors_support = normalize_cors(cors_raw)
                    free_access = normalize_free_access(auth_type, https_supported)

                    slug = name.lower().replace(" ", "-").replace("/", "-").replace("&", "and")
                    slug = "".join(c for c in slug if c.isalnum() or c in ("-", "_"))

                    normalized_records.append({
                        "slug": slug,
                        "name": name,
                        "description": desc,
                        "homepage_url": link,
                        "documentation_url": link,
                        "source": "public_apis",
                        "category": category,
                        "auth_type": auth_type,
                        "https_supported": https_supported,
                        "cors_support": cors_support,
                        "free_access": free_access,
                        "metadata_json": {
                            "original_category": category,
                            "original_auth": str(auth_raw)
                        }
                    })

        except Exception as e:
            logger.error(f"[Public APIs Adapter] Exception while fetching catalog entries: {e}")
            return []

        return normalized_records
