from __future__ import annotations

from finance.config import STRIPE_PRICE_FAMILY, STRIPE_PRICE_PLUS

PLANS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_usd": 0,
        "features": ["accounts", "transactions", "budgets", "goals", "csv_export"],
    },
    "plus": {
        "name": "Plus",
        "price_usd": 4.99,
        "stripe_price_env": "STRIPE_PRICE_PLUS",
        "features": [
            "accounts",
            "transactions",
            "budgets",
            "goals",
            "csv_export",
            "advanced_reports",
            "budget_alerts",
            "investments",
        ],
    },
    "family": {
        "name": "Family",
        "price_usd": 9.99,
        "stripe_price_env": "STRIPE_PRICE_FAMILY",
        "features": [
            "accounts",
            "transactions",
            "budgets",
            "goals",
            "csv_export",
            "advanced_reports",
            "budget_alerts",
            "investments",
            "shared_budgets",
            "priority_support",
        ],
    },
}

PLAN_RANK = {"free": 0, "plus": 1, "family": 2}


def stripe_price_for_plan(plan: str) -> str:
    if plan == "plus":
        return STRIPE_PRICE_PLUS
    if plan == "family":
        return STRIPE_PRICE_FAMILY
    return ""


def plan_from_stripe_price(price_id: str) -> str | None:
    if price_id and price_id == STRIPE_PRICE_PLUS:
        return "plus"
    if price_id and price_id == STRIPE_PRICE_FAMILY:
        return "family"
    return None


def has_feature(plan: str, feature: str) -> bool:
    return feature in PLANS.get(plan, PLANS["free"])["features"]


def is_active_subscription(status: str) -> bool:
    return status in {"active", "trialing", "manual"}
