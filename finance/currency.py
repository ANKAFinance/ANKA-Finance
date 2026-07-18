from __future__ import annotations

SUPPORTED_CURRENCIES: dict[str, dict[str, str]] = {
    "USD": {"symbol": "$", "name": "US Dollar", "locale": "en-US"},
    "EUR": {"symbol": "€", "name": "Euro", "locale": "de-DE"},
    "GBP": {"symbol": "£", "name": "British Pound", "locale": "en-GB"},
    "INR": {"symbol": "₹", "name": "Indian Rupee", "locale": "en-IN"},
    "CAD": {"symbol": "CA$", "name": "Canadian Dollar", "locale": "en-CA"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar", "locale": "en-AU"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen", "locale": "ja-JP"},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar", "locale": "en-SG"},
    "AED": {"symbol": "د.إ", "name": "UAE Dirham", "locale": "ar-AE"},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc", "locale": "de-CH"},
}


def normalize_currency(code: str | None, default: str = "USD") -> str:
    normalized = (code or default).upper()
    return normalized if normalized in SUPPORTED_CURRENCIES else default


def format_money(amount: float | int | None, currency_code: str = "USD") -> str:
    value = round(float(amount or 0), 2)
    code = normalize_currency(currency_code)
    meta = SUPPORTED_CURRENCIES[code]
    if code == "JPY":
        return f"{meta['symbol']}{value:,.0f}"
    return f"{meta['symbol']}{value:,.2f} {code}"
