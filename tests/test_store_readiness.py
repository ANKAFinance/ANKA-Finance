from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_app_config_uses_non_placeholder_bundle_ids() -> None:
    app_json = json.loads((ROOT / "mobile" / "app.json").read_text(encoding="utf-8"))
    expo = app_json["expo"]

    assert expo["ios"]["bundleIdentifier"] != "com.financetracker.app"
    assert expo["android"]["package"] != "com.financetracker.app"


def test_support_email_is_production_ready() -> None:
    from finance.config import SUPPORT_EMAIL

    assert SUPPORT_EMAIL != "support@example.com"
    assert "@" in SUPPORT_EMAIL


def test_legal_pages_use_real_support_contact() -> None:
    privacy = (ROOT / "templates" / "privacy.html").read_text(encoding="utf-8")
    terms = (ROOT / "templates" / "terms.html").read_text(encoding="utf-8")

    assert "support@example.com" not in privacy
    assert "support@example.com" not in terms
