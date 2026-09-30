"""Financial feature boundary: no market or trade claims without a real adapter."""
from typing import Any
from backend.security.approval_engine import approval_engine

class GovernedFinancialEngine:
    def __init__(self, approval_engine_instance=None):
        self.approval_engine = approval_engine_instance or approval_engine
        self.connected_broker = None

    def connect_broker_account(self, provider: str, oauth_token: str) -> dict[str, Any]:
        return {"success": False, "error": "Broker integration is unavailable in this release; no account was connected."}

    def research_market_and_dividends(self, query: str) -> dict[str, Any]:
        return {"success": False, "query": query, "candidates": [],
                "error": "A verified market-data provider is required; no market figures are available."}

    def draft_order_preview(self, symbol, action, shares, limit_price):
        return {"success": False, "error": "Broker integration is unavailable; no order was created."}

    def execute_approved_order(self, approval_id):
        return {"success": False, "error": "Broker execution is unavailable; no trade was executed."}

financial_engine = GovernedFinancialEngine()
