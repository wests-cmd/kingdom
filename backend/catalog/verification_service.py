"""
API Provider Verification Service.
Performs non-destructive reachability checks and updates provider verification status.
"""

import time
import uuid
import logging
import httpx
from typing import Dict, Any, Optional
from backend.catalog.repository import catalog_repo

logger = logging.getLogger(__name__)


class VerificationService:
    def __init__(self, repository=None):
        self.repo = repository or catalog_repo

    def verify_provider(self, provider_id: str) -> Dict[str, Any]:
        """Performs non-destructive GET/HEAD request to check provider documentation or homepage reachability."""
        provider = self.repo.get_api_provider(provider_id)
        if not provider:
            raise ValueError(f"API Provider '{provider_id}' not found.")

        target_url = provider.get("documentation_url") or provider.get("homepage_url")
        now = time.time()
        v_id = f"verif-{uuid.uuid4().hex[:8]}"

        if not target_url:
            with self.repo.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO api_verifications (id, api_provider_id, checked_at, reachable, https_valid, documentation_reachable, error)
                    VALUES (?, ?, ?, 0, 0, 0, 'No valid URL provided')
                """, (v_id, provider["id"], now))
                cursor.execute("""
                    UPDATE api_providers SET last_verified_at = ?, verification_status = 'failed' WHERE id = ?
                """, (now, provider["id"]))
                conn.commit()
            return {"provider_id": provider["id"], "reachable": False, "status": "failed", "error": "No valid URL provided"}

        reachable = False
        https_valid = target_url.startswith("https://")
        response_time_ms = None
        error_msg = None

        try:
            start_time = time.time()
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                resp = client.get(target_url)
                response_time_ms = round((time.time() - start_time) * 1000, 2)
                if resp.status_code < 500:
                    reachable = True
                else:
                    error_msg = f"HTTP {resp.status_code}"
        except Exception as e:
            error_msg = str(e)

        v_status = "verified" if reachable else "failed"

        with self.repo.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_verifications (id, api_provider_id, checked_at, reachable, https_valid, documentation_reachable, response_time_ms, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (v_id, provider["id"], now, 1 if reachable else 0, 1 if https_valid else 0, 1 if reachable else 0, response_time_ms, error_msg))
            cursor.execute("""
                UPDATE api_providers SET last_verified_at = ?, verification_status = ?, status = ? WHERE id = ?
            """, (now, v_status, "verified" if reachable else "degraded", provider["id"]))
            conn.commit()

        return {
            "provider_id": provider["id"],
            "target_url": target_url,
            "reachable": reachable,
            "https_valid": https_valid,
            "response_time_ms": response_time_ms,
            "verification_status": v_status,
            "error": error_msg
        }


verification_service = VerificationService()
