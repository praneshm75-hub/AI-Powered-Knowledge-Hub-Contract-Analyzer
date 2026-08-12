import time
import json
import hashlib
import secrets
from typing import Dict, Any, List, Tuple

class SubscriptionManager:
    """
    Manages user subscription tiers (Free, Pro, Enterprise), checkout sessions,
    usage quotas, and live Stripe webhook log event dispatching.
    """

    TIERS = {
        "FREE": {
            "name": "Free Tier",
            "price": "$0/mo",
            "upload_limit": 10,
            "query_daily_limit": 50,
            "max_pages_per_doc": 50,
            "clause_risk_radar": True,
            "custom_pgvector": False,
            "webhooks": False
        },
        "PRO": {
            "name": "Pro Tier",
            "price": "$29/mo",
            "upload_limit": 50,
            "query_daily_limit": 100,
            "max_pages_per_doc": 200,
            "clause_risk_radar": True,
            "custom_pgvector": False,
            "webhooks": False
        },
        "ENTERPRISE": {
            "name": "Enterprise Tier",
            "price": "$199/mo",
            "upload_limit": 9999,
            "query_daily_limit": 9999,
            "max_pages_per_doc": 9999,
            "clause_risk_radar": True,
            "custom_pgvector": True,
            "webhooks": True
        }
    }

    def __init__(self):
        self.active_user = {
            "id": "usr_9981",
            "name": "Alex Mercer",
            "email": "alex.mercer@apextech.io",
            "provider": "Google OAuth",
            "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
            "tier": "FREE",
            "uploads_used": 1,
            "queries_today": 0,
            "max_queries": 50,
            "max_uploads": 10
        }
        self.webhook_logs: List[Dict[str, Any]] = []
        self._add_initial_webhooks()

    def _add_initial_webhooks(self):
        self.dispatch_webhook("customer.subscription.created", {
            "customer_id": "cus_N7XyZ9a8",
            "plan": "Free Tier",
            "status": "active",
            "created_at": int(time.time()) - 86400
        })

    def get_profile(self) -> Dict[str, Any]:
        tier_info = self.TIERS[self.active_user["tier"]]
        return {
            **self.active_user,
            "tier_details": tier_info,
            "queries_remaining": max(0, tier_info["query_daily_limit"] - self.active_user["queries_today"]),
            "uploads_remaining": max(0, tier_info["upload_limit"] - self.active_user["uploads_used"])
        }

    def switch_oauth_provider(self, provider_name: str) -> Dict[str, Any]:
        if "github" in provider_name.lower():
            self.active_user["provider"] = "GitHub OAuth"
            self.active_user["name"] = "alex-mercer-dev"
            self.active_user["email"] = "alex.dev@github.com"
        elif "enterprise" in provider_name.lower() or "sso" in provider_name.lower():
            self.active_user["provider"] = "Enterprise Okta SSO"
            self.active_user["name"] = "Alex Mercer (Legal Director)"
            self.active_user["email"] = "amercer@globalcorp-legal.com"
            self.active_user["tier"] = "ENTERPRISE"
        else:
            self.active_user["provider"] = "Google OAuth"
            self.active_user["name"] = "Alex Mercer"
            self.active_user["email"] = "alex.mercer@apextech.io"
        return self.get_profile()

    def check_query_allowed(self) -> Tuple[bool, str]:
        tier_info = self.TIERS[self.active_user["tier"]]
        if self.active_user["queries_today"] >= tier_info["query_daily_limit"]:
            return False, f"Query quota exceeded ({self.active_user['queries_today']}/{tier_info['query_daily_limit']}). Upgrade to Pro for unlimited AI queries."
        self.active_user["queries_today"] += 1
        return True, "Allowed"

    def upgrade_subscription(self, target_tier: str, card_last4: str = "4242") -> Dict[str, Any]:
        target_tier = target_tier.upper()
        if target_tier not in self.TIERS:
            target_tier = "PRO"

        prev_tier = self.active_user["tier"]
        self.active_user["tier"] = target_tier
        
        # Reset counters on upgrade
        self.active_user["queries_today"] = 0
        self.active_user["uploads_used"] = 1

        # Dispatch Stripe Webhook Events
        evt_session = self.dispatch_webhook("checkout.session.completed", {
            "checkout_id": f"cs_test_{secrets.token_hex(8)}",
            "customer_email": self.active_user["email"],
            "amount_total": 2900 if target_tier == "PRO" else 19900,
            "currency": "usd",
            "card_last4": card_last4,
            "payment_status": "paid"
        })

        evt_sub = self.dispatch_webhook("customer.subscription.updated", {
            "subscription_id": f"sub_{secrets.token_hex(8)}",
            "previous_tier": prev_tier,
            "new_tier": target_tier,
            "status": "active",
            "current_period_end": int(time.time()) + (30 * 86400)
        })

        return {
            "success": True,
            "message": f"Successfully upgraded to {self.TIERS[target_tier]['name']}!",
            "profile": self.get_profile(),
            "triggered_webhooks": [evt_session["id"], evt_sub["id"]]
        }

    def dispatch_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_id = f"evt_{secrets.token_hex(10)}"
        timestamp = int(time.time())
        raw_body = json.dumps(payload)
        sig = hashlib.sha256(f"whsec_secret_12345_{timestamp}_{raw_body}".encode()).hexdigest()

        log_entry = {
            "id": event_id,
            "type": event_type,
            "timestamp": timestamp,
            "signature": f"t={timestamp},v1={sig[:32]}...",
            "payload": payload,
            "status": "200_OK_VERIFIED"
        }
        self.webhook_logs.insert(0, log_entry)
        if len(self.webhook_logs) > 20:
            self.webhook_logs.pop()
        return log_entry
