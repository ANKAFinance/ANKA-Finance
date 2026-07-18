from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "PersonalFinanceTracker"
DB_PATH = Path(os.environ.get("FINANCE_TRACKER_DB", DEFAULT_DATA_DIR / "finance.db"))

SECRET_KEY = os.environ.get("SECRET_KEY", "replace-this-secret-key")
JWT_SECRET = os.environ.get("JWT_SECRET", SECRET_KEY)
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "720"))

APP_URL = os.environ.get("APP_URL", "https://app.financetracker.app").rstrip("/")
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
APP_NAME = os.environ.get("APP_NAME", "Personal Finance Tracker")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@financetracker.app")
PRIVACY_URL = os.environ.get("PRIVACY_URL", f"{APP_URL}/privacy")
TERMS_URL = os.environ.get("TERMS_URL", f"{APP_URL}/terms")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PLUS = os.environ.get("STRIPE_PRICE_PLUS", "")
STRIPE_PRICE_FAMILY = os.environ.get("STRIPE_PRICE_FAMILY", "")

APPLE_SHARED_SECRET = os.environ.get("APPLE_SHARED_SECRET", "")
GOOGLE_PLAY_PACKAGE = os.environ.get("GOOGLE_PLAY_PACKAGE", "com.advait.personalfinancetracker")
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")

DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")
