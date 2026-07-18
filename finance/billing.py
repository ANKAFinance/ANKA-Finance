from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone

from finance.config import (
    APP_URL,
    STRIPE_PRICE_FAMILY,
    STRIPE_PRICE_PLUS,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from finance.db import get_db, update_subscription
from finance.plans import plan_from_stripe_price

stripe = None
if STRIPE_SECRET_KEY:
    import stripe as stripe_sdk

    stripe_sdk.api_key = STRIPE_SECRET_KEY
    stripe = stripe_sdk


def stripe_enabled() -> bool:
    return stripe is not None and bool(STRIPE_SECRET_KEY)


def create_checkout_session(user_id: int, email: str, plan: str) -> str | None:
    if not stripe_enabled():
        return None
    price_id = STRIPE_PRICE_PLUS if plan == "plus" else STRIPE_PRICE_FAMILY if plan == "family" else ""
    if not price_id:
        return None

    with closing(get_db()) as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        customer_id = user["stripe_customer_id"] if user else None

    if not customer_id:
        customer = stripe.Customer.create(email=email, metadata={"user_id": str(user_id)})
        customer_id = customer.id
        with closing(get_db()) as conn:
            conn.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (customer_id, user_id),
            )
            conn.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{APP_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/pricing",
        metadata={"user_id": str(user_id), "plan": plan},
        allow_promotion_codes=True,
    )
    return session.url


def create_customer_portal(user_id: int) -> str | None:
    if not stripe_enabled():
        return None
    with closing(get_db()) as conn:
        user = conn.execute("SELECT stripe_customer_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or not user["stripe_customer_id"]:
        return None
    session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{APP_URL}/settings",
    )
    return session.url


def handle_webhook(payload: bytes, signature: str) -> tuple[bool, str]:
    if not stripe_enabled():
        return False, "Stripe is not configured."
    if not STRIPE_WEBHOOK_SECRET:
        return False, "Webhook secret is not configured."

    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return False, "Invalid payload."
    except stripe.error.SignatureVerificationError:
        return False, "Invalid signature."

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _sync_checkout_session(data)
    elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        _sync_subscription(data)
    elif event_type == "customer.subscription.deleted":
        _cancel_subscription(data)

    return True, "ok"


def _user_id_from_customer(customer_id: str) -> int | None:
    with closing(get_db()) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE stripe_customer_id = ?",
            (customer_id,),
        ).fetchone()
    return int(row["id"]) if row else None


def _sync_checkout_session(session: dict) -> None:
    user_id = session.get("metadata", {}).get("user_id")
    plan = session.get("metadata", {}).get("plan", "plus")
    if not user_id:
        return
    subscription_id = session.get("subscription")
    update_subscription(
        int(user_id),
        plan=plan,
        status="active",
        provider="stripe",
        stripe_customer_id=session.get("customer"),
        stripe_subscription_id=subscription_id,
    )


def _sync_subscription(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    user_id = _user_id_from_customer(customer_id) if customer_id else None
    if not user_id:
        return

    price_id = subscription["items"]["data"][0]["price"]["id"] if subscription.get("items") else ""
    plan = plan_from_stripe_price(price_id) or "plus"
    status = subscription.get("status", "active")
    period_end = subscription.get("current_period_end")
    expires_at = (
        datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else None
    )

    update_subscription(
        user_id,
        plan=plan if status in {"active", "trialing"} else "free",
        status=status,
        provider="stripe",
        stripe_subscription_id=subscription.get("id"),
        expires_at=expires_at,
    )


def _cancel_subscription(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    user_id = _user_id_from_customer(customer_id) if customer_id else None
    if not user_id:
        return
    update_subscription(
        user_id,
        plan="free",
        status="canceled",
        provider="stripe",
        stripe_subscription_id=subscription.get("id"),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
