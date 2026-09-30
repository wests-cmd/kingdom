"""
Catalog and Profile Database Repository.
Manages profiles, capabilities, providers, mappings, user active profiles, sync logs, and verifications.
"""

import json
import time
import uuid
from typing import Optional, List, Dict, Any
from backend.storage.db import db
from backend.catalog.models import (
    Profile,
    Capability,
    ProfileCapability,
    UserProfile,
    ApiProvider,
    ApiCapability,
    CatalogSyncRecord,
    ApiVerificationRecord
)


class CatalogRepository:
    def __init__(self, database=None):
        self.db = database or db
        self.seed_defaults()

    def seed_defaults(self):
        """Seeds standard built-in capability vocabulary and 12 system profiles if missing."""
        now = time.time()
        initial_capabilities = [
            ("web_search", "Web Search", "General web search and indexing", "search", "low", 0, 0, 1),
            ("research", "Deep Research", "Multi-source synthesis and comprehensive research", "research", "low", 0, 0, 1),
            ("news_search", "News & Current Events", "Live headlines and news article aggregation", "news", "low", 0, 0, 1),
            ("product_search", "Product Search", "E-commerce product catalog search", "shopping", "low", 0, 0, 1),
            ("product_research", "Product Research", "Item specifications, review sentiment, and merchant comparison", "shopping", "low", 0, 0, 1),
            ("price_comparison", "Price Comparison", "Historical and current price comparison across markets", "shopping", "low", 0, 0, 1),
            ("market_research", "Market Research", "Industry metrics, trend analysis, and competitor intelligence", "business", "medium", 0, 0, 1),
            ("financial_data", "Financial & Stock Data", "Stock quotes, market indices, exchange rates, and financial reports", "finance", "medium", 0, 0, 1),
            ("weather_lookup", "Weather & Forecasts", "Live weather conditions, radar, and climate forecasts", "location", "low", 0, 0, 1),
            ("geolocation", "Geolocation & Maps", "Geocoding, route planning, and spatial intelligence", "location", "low", 0, 0, 1),
            ("travel_information", "Travel & Transit", "Flight statuses, transit schedules, and travel advisories", "travel", "low", 0, 0, 1),
            ("image_search", "Image Search", "Visual media and image search", "media", "low", 0, 0, 1),
            ("image_generation", "Image Generation", "Generative media creation and image synthesis", "media", "medium", 0, 0, 0),
            ("book_search", "Books & Publications", "Literary catalogs, ISBN lookups, and citation metadata", "education", "low", 0, 0, 1),
            ("science_data", "Scientific Data & Papers", "Academic papers, arXiv publications, and scientific datasets", "education", "low", 0, 0, 1),
            ("translation", "Language Translation", "Multi-language text translation and localization", "language", "low", 0, 0, 1),
            ("text_analysis", "Text & Sentiment Analysis", "Document summarization, entity extraction, and sentiment scoring", "language", "low", 0, 0, 1),
            ("code_analysis", "Code & Repo Analysis", "Syntax inspection, bug detection, and code repository intelligence", "development", "medium", 0, 0, 1),
            ("community_moderation", "Community & Content Moderation", "Automated moderation, spam detection, and community safety", "community", "low", 0, 0, 1)
        ]

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for slug, name, desc, cat, risk, req_auth, req_app, read_only in initial_capabilities:
                cap_id = f"cap-{slug}"
                cursor.execute("SELECT id FROM capabilities WHERE slug = ?", (slug,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO capabilities (id, slug, name, description, category, risk_level, requires_auth, requires_approval, read_only, enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (cap_id, slug, name, desc, cat, risk, req_auth, req_app, read_only, now, now))

            system_profiles = [
                ("general_assistant", "General Assistant", "Versatile assistant for everyday tasks, questions, and search.", "bot", ["web_search", "weather_lookup", "translation", "text_analysis"]),
                ("researcher", "Researcher", "Information gathering, deep synthesis, academic search, and paper analysis.", "search", ["web_search", "research", "news_search", "science_data", "book_search", "text_analysis"]),
                ("student_learner", "Student / Learner", "Educational learning, scientific research, book search, and explanations.", "book-open", ["web_search", "research", "science_data", "book_search", "translation"]),
                ("developer", "Developer", "Code analysis, technical documentation, API discovery, and repository intelligence.", "code", ["web_search", "code_analysis", "text_analysis", "research"]),
                ("business", "Business", "Market intelligence, competitor research, text analysis, and financial data.", "briefcase", ["web_search", "market_research", "financial_data", "text_analysis", "news_search"]),
                ("reseller_buyer_seller", "Reseller / Buyer-Seller", "Product research, price comparison, market trends, and e-commerce lookups.", "shopping-bag", ["web_search", "product_search", "product_research", "price_comparison", "market_research"]),
                ("market_research", "Market Research", "In-depth market metrics, industry trends, and consumer sentiment.", "bar-chart-2", ["web_search", "market_research", "product_research", "news_search", "financial_data"]),
                ("finance_market_watch", "Finance / Market Watch", "Financial quotes, market tracking, currency exchange, and news updates.", "trending-up", ["web_search", "financial_data", "news_search", "market_research"]),
                ("news_information", "News & Information", "Live news feeds, headlines, media search, and topic monitoring.", "newspaper", ["web_search", "news_search", "text_analysis", "media_search"]),
                ("travel_location", "Travel & Location", "Flight tracking, transit info, geolocation, weather, and local exploration.", "map-pin", ["web_search", "geolocation", "weather_lookup", "travel_information"]),
                ("creator", "Creator", "Generative media ideas, image generation, text analysis, and creative research.", "image", ["web_search", "image_search", "image_generation", "text_analysis", "translation"]),
                ("community_moderator", "Discord / Community", "Community moderation, sentiment tracking, text analysis, and safety checks.", "users", ["web_search", "community_moderation", "text_analysis", "news_search"])
            ]

            for slug, name, desc, icon, cap_slugs in system_profiles:
                p_id = f"prof-{slug}"
                cursor.execute("SELECT id FROM profiles WHERE slug = ?", (slug,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO profiles (id, slug, name, description, icon, system, status, version, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, 'active', 1, ?, ?)
                    """, (p_id, slug, name, desc, icon, now, now))

                    for idx, cap_slug in enumerate(cap_slugs):
                        cursor.execute("SELECT id FROM capabilities WHERE slug = ?", (cap_slug,))
                        cap_row = cursor.fetchone()
                        if cap_row:
                            c_id = cap_row[0]
                            cursor.execute("""
                                INSERT OR IGNORE INTO profile_capabilities (profile_id, capability_id, priority, required, mode, created_at)
                                VALUES (?, ?, ?, 0, 'recommend', ?)
                            """, (p_id, c_id, idx, now))

            # Ensure default user profile exists
            cursor.execute("SELECT id FROM user_profiles WHERE user_id = 'default_user' AND is_default = 1")
            if not cursor.fetchone():
                gen_p_id = "prof-general_assistant"
                up_id = "uprof-default"
                cursor.execute("""
                    INSERT INTO user_profiles (id, user_id, profile_id, name, enabled, is_default, preferences_json, created_at, updated_at)
                    VALUES (?, 'default_user', ?, 'Default General Profile', 1, 1, '{}', ?, ?)
                """, (up_id, gen_p_id, now, now))

            conn.commit()

    # --- Profiles Methods ---

    def list_profiles(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles ORDER BY system DESC, name ASC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE id = ? OR slug = ?", (profile_id, profile_id))
            row = cursor.fetchone()
            if not row:
                return None
            p = dict(row)
            # Fetch profile capabilities
            cursor.execute("""
                SELECT c.*, pc.priority, pc.required, pc.mode
                FROM profile_capabilities pc
                JOIN capabilities c ON pc.capability_id = c.id
                WHERE pc.profile_id = ?
                ORDER BY pc.priority ASC
            """, (p["id"],))
            p["capabilities"] = [dict(r) for r in cursor.fetchall()]
            return p

    def create_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        p_id = data.get("id") or f"prof-{uuid.uuid4().hex[:8]}"
        slug = data.get("slug") or data["name"].lower().replace(" ", "_")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO profiles (id, slug, name, description, icon, system, status, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (p_id, slug, data["name"], data.get("description", ""), data.get("icon", "zap"), 1 if data.get("system") else 0, data.get("status", "active"), now, now))

            capabilities = data.get("capabilities", [])
            for idx, c_id in enumerate(capabilities):
                cursor.execute("""
                    INSERT OR IGNORE INTO profile_capabilities (profile_id, capability_id, priority, required, mode, created_at)
                    VALUES (?, ?, ?, 0, 'recommend', ?)
                """, (p_id, c_id, idx, now))
            conn.commit()
        return self.get_profile(p_id)

    # --- User Active Profile ---

    def get_active_user_profile(self, user_id: str = "default_user") -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT up.*, p.slug as profile_slug, p.name as profile_name, p.description as profile_description, p.icon as profile_icon
                FROM user_profiles up
                JOIN profiles p ON up.profile_id = p.id
                WHERE up.user_id = ? AND up.is_default = 1
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return self.get_profile("prof-general_assistant")
            up = dict(row)
            up["profile_details"] = self.get_profile(up["profile_id"])
            return up

    def set_active_user_profile(self, profile_id: str, user_id: str = "default_user") -> Dict[str, Any]:
        now = time.time()
        p = self.get_profile(profile_id)
        if not p:
            raise ValueError(f"Profile '{profile_id}' not found.")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE user_profiles SET is_default = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("SELECT id FROM user_profiles WHERE user_id = ? AND profile_id = ?", (user_id, p["id"]))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE user_profiles SET is_default = 1, enabled = 1, updated_at = ? WHERE id = ?", (now, row[0]))
            else:
                up_id = f"uprof-{uuid.uuid4().hex[:8]}"
                cursor.execute("""
                    INSERT INTO user_profiles (id, user_id, profile_id, name, enabled, is_default, preferences_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, 1, '{}', ?, ?)
                """, (up_id, user_id, p["id"], f"Active {p['name']}", now, now))
            conn.commit()

        return self.get_active_user_profile(user_id)

    # --- Capabilities Methods ---

    def list_capabilities(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM capabilities WHERE enabled = 1 ORDER BY category ASC, name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_capability(self, capability_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM capabilities WHERE id = ? OR slug = ?", (capability_id, capability_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- API Providers Catalog ---

    def list_api_providers(self, category: Optional[str] = None, capability_slug: Optional[str] = None, verified_only: bool = False) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT DISTINCT ap.* FROM api_providers ap"
            params = []
            where_clauses = ["ap.status != 'disabled'"]

            if capability_slug:
                query += " JOIN api_capabilities ac ON ap.id = ac.api_provider_id JOIN capabilities c ON ac.capability_id = c.id"
                where_clauses.append("(c.slug = ? OR c.id = ?)")
                params.extend([capability_slug, capability_slug])

            if category:
                where_clauses.append("ap.category = ?")
                params.append(category)

            if verified_only:
                where_clauses.append("ap.verification_status = 'verified'")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            query += " ORDER BY ap.name ASC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def upsert_api_provider(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        slug = data["slug"]
        p_id = data.get("id") or f"apiprovider-{slug}"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM api_providers WHERE slug = ?", (slug,))
            existing = cursor.fetchone()

            metadata_str = json.dumps(data.get("metadata_json", {})) if isinstance(data.get("metadata_json"), dict) else data.get("metadata_json", "{}")

            if existing:
                cursor.execute("""
                    UPDATE api_providers
                    SET name = ?, description = ?, homepage_url = ?, documentation_url = ?, source = ?, category = ?,
                        auth_type = ?, https_supported = ?, cors_support = ?, free_access = ?, metadata_json = ?, updated_at = ?
                    WHERE slug = ?
                """, (
                    data["name"], data.get("description"), data.get("homepage_url"), data.get("documentation_url"),
                    data.get("source", "public_apis"), data.get("category", "General"), data.get("auth_type", "none"),
                    1 if data.get("https_supported", True) else 0, str(data.get("cors_support", "unknown")),
                    data.get("free_access", "unknown"), metadata_str, now, slug
                ))
                p_id = existing[0]
            else:
                cursor.execute("""
                    INSERT INTO api_providers (id, slug, name, description, homepage_url, documentation_url, source, category, auth_type, https_supported, cors_support, free_access, status, last_verified_at, verification_status, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL, 'unverified', ?, ?, ?)
                """, (
                    p_id, slug, data["name"], data.get("description"), data.get("homepage_url"), data.get("documentation_url"),
                    data.get("source", "public_apis"), data.get("category", "General"), data.get("auth_type", "none"),
                    1 if data.get("https_supported", True) else 0, str(data.get("cors_support", "unknown")),
                    data.get("free_access", "unknown"), metadata_str, now, now
                ))
            conn.commit()

        return self.get_api_provider(p_id)

    def get_api_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_providers WHERE id = ? OR slug = ?", (provider_id, provider_id))
            row = cursor.fetchone()
            if not row:
                return None
            p = dict(row)
            cursor.execute("""
                SELECT c.*, ac.confidence, ac.verified
                FROM api_capabilities ac
                JOIN capabilities c ON ac.capability_id = c.id
                WHERE ac.api_provider_id = ?
            """, (p["id"],))
            p["capabilities"] = [dict(r) for r in cursor.fetchall()]
            return p

    def link_api_capability(self, provider_id: str, capability_id: str, confidence: float = 1.0, verified: bool = False):
        now = time.time()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO api_capabilities (api_provider_id, capability_id, confidence, mapping_source, verified, created_at)
                VALUES (?, ?, ?, 'catalog', ?, ?)
            """, (provider_id, capability_id, confidence, 1 if verified else 0, now))
            conn.commit()

    # --- Sync & Verification Logging ---

    def create_sync_record(self, source: str) -> str:
        s_id = f"sync-{uuid.uuid4().hex[:8]}"
        now = time.time()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_catalog_syncs (id, source, started_at, status)
                VALUES (?, ?, ?, 'running')
            """, (s_id, source, now))
            conn.commit()
        return s_id

    def update_sync_record(self, s_id: str, status: str, seen: int = 0, added: int = 0, updated: int = 0, disabled: int = 0, errors: Optional[str] = None):
        now = time.time()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE api_catalog_syncs
                SET status = ?, completed_at = ?, entries_seen = ?, entries_added = ?, entries_updated = ?, entries_disabled = ?, errors = ?
                WHERE id = ?
            """, (status, now, seen, added, updated, disabled, errors, s_id))
            conn.commit()

    def get_last_sync_record(self, source: str = "public_apis") -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_catalog_syncs WHERE source = ? ORDER BY started_at DESC LIMIT 1", (source,))
            row = cursor.fetchone()
            return dict(row) if row else None


catalog_repo = CatalogRepository()
