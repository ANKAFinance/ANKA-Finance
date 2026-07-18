from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

import requests

from finance.config import APPLE_SHARED_SECRET, GOOGLE_PLAY_PACKAGE, GOOGLE_PLAY_SERVICE_ACCOUNT_JSON
from finance.db import get_db, update_subscription

MOBILE_PRODUCTS = {
    "com.advait.personalfinancetracker.plus.monthly": "plus",
    "com.advait.personalfinancetracker.family.monthly": "family",
}

APPLE_PRODUCTION_VERIFY_URL = "https://buy.itunes.apple.com/verifyReceipt"
APPLE_SANDBOX_VERIFY_URL = "https://sandbox.itunes.apple.com/verifyReceipt"


def _ms_to_iso(value: str | int | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _verify_apple_receipt(payload: dict) -> tuple[bool, str, dict]:
    receipt_data = payload.get("receipt_data") or payload.get("transaction_receipt")
    if not APPLE_SHARED_SECRET:
        return False, "Apple shared secret is not configured.", {}
    if not receipt_data:
        return False, "Apple receipt data is required.", {}

    body = {
        "receipt-data": receipt_data,
        "password": APPLE_SHARED_SECRET,
        "exclude-old-transactions": True,
    }

    try:
        response = requests.post(APPLE_PRODUCTION_VERIFY_URL, json=body, timeout=10)
        data = response.json()
        if data.get("status") == 21007:
            response = requests.post(APPLE_SANDBOX_VERIFY_URL, json=body, timeout=10)
            data = response.json()
    except requests.RequestException:
        return False, "Could not verify Apple receipt.", {}

    if data.get("status") != 0:
        return False, "Apple receipt was rejected.", data

    purchases = data.get("latest_receipt_info") or []
    matching = [
        item for item in purchases
        if item.get("product_id") in MOBILE_PRODUCTS
    ]
    if not matching:
        return False, "No supported subscription found in Apple receipt.", data

    latest = max(matching, key=lambda item: int(item.get("expires_date_ms") or 0))
    expires_at = _ms_to_iso(latest.get("expires_date_ms"))
    if not expires_at:
        return False, "Apple subscription expiry is missing.", data

    return True, "Apple subscription verified.", {
        "product_id": latest.get("product_id"),
        "transaction_id": latest.get("original_transaction_id") or latest.get("transaction_id"),
        "expires_at": expires_at,
        "raw": data,
    }


def _google_access_token() -> str | None:
    if not GOOGLE_PLAY_SERVICE_ACCOUNT_JSON:
        return None
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request

        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_PLAY_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
        credentials.refresh(Request())
        return credentials.token
    except Exception:
        return None


def _verify_google_purchase(payload: dict) -> tuple[bool, str, dict]:
    product_id = payload.get("product_id", "")
    purchase_token = payload.get("purchase_token", "")
    if not GOOGLE_PLAY_SERVICE_ACCOUNT_JSON:
        return False, "Google Play service account is not configured.", {}
    if product_id not in MOBILE_PRODUCTS or not purchase_token:
        return False, "Google Play product and purchase token are required.", {}

    access_token = _google_access_token()
    if not access_token:
        return False, "Could not authenticate with Google Play.", {}

    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{GOOGLE_PLAY_PACKAGE}/purchases/subscriptions/{product_id}/tokens/{purchase_token}"
    )
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        data = response.json()
    except requests.RequestException:
        return False, "Could not verify Google Play purchase.", {}

    if response.status_code != 200:
        return False, "Google Play purchase was rejected.", data

    expires_at = _ms_to_iso(data.get("expiryTimeMillis"))
    if not expires_at:
        return False, "Google Play subscription expiry is missing.", data
    if data.get("paymentState") not in {1, 2, None}:
        return False, "Google Play subscription is not active.", data

    return True, "Google Play subscription verified.", {
        "product_id": product_id,
        "transaction_id": data.get("orderId") or purchase_token,
        "expires_at": expires_at,
        "raw": data,
    }


def verify_mobile_purchase(user_id: int, provider: str, payload: dict) -> tuple[bool, str]:
    provider = provider.lower()
    if provider not in {"apple", "google"}:
        return False, "Unsupported provider."

    if provider == "apple":
        verified, message, verified_payload = _verify_apple_receipt(payload)
    else:
        verified, message, verified_payload = _verify_google_purchase(payload)
    if not verified:
        return False, message

    product_id = verified_payload.get("product_id", "")
    transaction_id = verified_payload.get("transaction_id", "")
    plan = MOBILE_PRODUCTS.get(product_id)
    if not plan or not transaction_id:
        return False, "Invalid verified product or transaction."

    with closing(get_db()) as conn:
        existing = conn.execute(
            "SELECT id FROM mobile_receipts WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        if existing:
            return True, "Already verified."

    expires_at = verified_payload.get("expires_at")
    if not expires_at:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    update_subscription(
        user_id,
        plan=plan,
        status="active",
        provider=provider,
        expires_at=expires_at,
    )

    with closing(get_db()) as conn:
        conn.execute(
            """
            INSERT INTO mobile_receipts
                (user_id, provider, product_id, transaction_id, plan, expires_at, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, provider, product_id, transaction_id, plan, expires_at, json.dumps(verified_payload.get("raw", {}))),
        )
        conn.commit()

    return True, message
