from __future__ import annotations

from contextlib import closing
from datetime import date

from flask import Blueprint, g, jsonify, request

from finance.auth import api_login_required, authenticate_user, create_access_token, register_user
from finance.billing import create_checkout_session, create_customer_portal, stripe_enabled
from finance.config import APP_NAME, PRIVACY_URL, SUPPORT_EMAIL, TERMS_URL
from finance.currency import SUPPORTED_CURRENCIES, normalize_currency
from finance.db import delete_user_account, effective_plan, get_db, money, user_to_dict
from finance.mobile_billing import MOBILE_PRODUCTS, verify_mobile_purchase
from finance.plans import PLANS, has_feature

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

INCOME_CATEGORIES = [
    "Salary", "Freelance", "Investments", "Gifts", "Other Income",
]
EXPENSE_CATEGORIES = [
    "Housing", "Utilities", "Groceries", "Dining", "Transport", "Healthcare",
    "Insurance", "Subscriptions", "Shopping", "Education", "Entertainment",
    "Travel", "Savings", "Other Expense",
]
ACCOUNT_TYPES = ["Checking", "Savings", "Credit Card", "Cash", "Investment", "Loan", "Other"]


def _current_user():
    return g.api_user


def _user_payload(user) -> dict:
    data = user_to_dict(user)
    data["effective_plan"] = effective_plan(user)
    data["features"] = PLANS[data["effective_plan"]]["features"]
    return data


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok", "stripe": stripe_enabled()})


@api_bp.get("/meta")
def meta():
    return jsonify({
        "app": {
            "name": APP_NAME,
            "support_email": SUPPORT_EMAIL,
            "privacy_url": PRIVACY_URL,
            "terms_url": TERMS_URL,
        },
        "currencies": SUPPORTED_CURRENCIES,
        "plans": {k: {"name": v["name"], "price_usd": v["price_usd"], "features": v["features"]} for k, v in PLANS.items()},
        "mobile_products": MOBILE_PRODUCTS,
        "income_categories": INCOME_CATEGORIES,
        "expense_categories": EXPENSE_CATEGORIES,
        "account_types": ACCOUNT_TYPES,
    })


@api_bp.post("/auth/register")
def api_register():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    currency = normalize_currency(body.get("currency"))

    if not name or "@" not in email or len(password) < 8:
        return jsonify({"error": "Name, valid email, and 8+ character password required."}), 400
    try:
        user = register_user(name, email, password, currency)
    except Exception:
        return jsonify({"error": "An account with that email already exists."}), 409

    token = create_access_token(user["id"])
    return jsonify({"token": token, "user": user}), 201


@api_bp.post("/auth/login")
def api_login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    user = authenticate_user(email, password)
    if not user:
        return jsonify({"error": "Invalid credentials."}), 401
    token = create_access_token(user["id"])
    return jsonify({"token": token, "user": user})


@api_bp.get("/me")
@api_login_required
def api_me():
    return jsonify({"user": _user_payload(_current_user())})


@api_bp.patch("/me")
@api_login_required
def api_update_me():
    body = request.get_json(silent=True) or {}
    user = _current_user()
    name = (body.get("name") or user["name"]).strip()
    currency = normalize_currency(body.get("currency") or user["currency"])

    with closing(get_db()) as conn:
        conn.execute(
            "UPDATE users SET name = ?, currency = ? WHERE id = ?",
            (name, currency, user["id"]),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({"user": _user_payload(updated)})


@api_bp.delete("/me")
@api_login_required
def api_delete_me():
    delete_user_account(_current_user()["id"])
    return jsonify({"ok": True})


@api_bp.get("/dashboard")
@api_login_required
def api_dashboard():
    user = _current_user()
    user_id = user["id"]
    month_key = date.today().strftime("%Y-%m")

    with closing(get_db()) as conn:
        total_income = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ? AND type = 'income'",
            (user_id,),
        ).fetchone()[0]
        total_expenses = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ? AND type = 'expense'",
            (user_id,),
        ).fetchone()[0]
        net_worth = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE user_id = ? AND include_in_net_worth = 1",
            (user_id,),
        ).fetchone()[0]
        monthly_income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE user_id = ? AND type = 'income' AND substr(transaction_date, 1, 7) = ?
            """,
            (user_id, month_key),
        ).fetchone()[0]
        monthly_expenses = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE user_id = ? AND type = 'expense' AND substr(transaction_date, 1, 7) = ?
            """,
            (user_id, month_key),
        ).fetchone()[0]
        recent = conn.execute(
            """
            SELECT t.*, a.name AS account_name FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.user_id = ? ORDER BY t.transaction_date DESC, t.id DESC LIMIT 10
            """,
            (user_id,),
        ).fetchall()

    return jsonify({
        "total_income": money(total_income),
        "total_expenses": money(total_expenses),
        "balance": money(total_income - total_expenses),
        "net_worth": money(net_worth),
        "monthly_income": money(monthly_income),
        "monthly_expenses": money(monthly_expenses),
        "monthly_net": money(monthly_income - monthly_expenses),
        "recent_transactions": [dict(r) for r in recent],
        "currency": user["currency"],
    })


@api_bp.get("/transactions")
@api_login_required
def api_transactions():
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        rows = conn.execute(
            """
            SELECT t.*, a.name AS account_name FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.user_id = ? ORDER BY t.transaction_date DESC, t.id DESC
            """,
            (user_id,),
        ).fetchall()
    return jsonify({"transactions": [dict(r) for r in rows]})


@api_bp.post("/transactions")
@api_login_required
def api_create_transaction():
    body = request.get_json(silent=True) or {}
    user_id = _current_user()["id"]
    description = (body.get("description") or "").strip()
    amount = body.get("amount")
    category = (body.get("category") or "").strip()
    txn_type = body.get("type", "expense")
    account_id = body.get("account_id")
    transaction_date = body.get("transaction_date") or date.today().isoformat()
    notes = (body.get("notes") or "").strip()

    if not description or not amount or float(amount) <= 0 or txn_type not in {"income", "expense"}:
        return jsonify({"error": "Invalid transaction."}), 400

    with closing(get_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transactions
                (user_id, account_id, description, amount, category, type, transaction_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, account_id, description, float(amount), category, txn_type, transaction_date, notes),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"transaction": dict(row)}), 201


@api_bp.delete("/transactions/<int:transaction_id>")
@api_login_required
def api_delete_transaction(transaction_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (transaction_id, _current_user()["id"]),
        )
        conn.commit()
    return jsonify({"ok": True})


@api_bp.get("/accounts")
@api_login_required
def api_accounts():
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY type, name",
            (user_id,),
        ).fetchall()
    return jsonify({"accounts": [dict(r) for r in rows]})


@api_bp.post("/accounts")
@api_login_required
def api_create_account():
    body = request.get_json(silent=True) or {}
    user_id = _current_user()["id"]
    name = (body.get("name") or "").strip()
    account_type = body.get("type", "Checking")
    balance = body.get("balance", 0)
    include = 1 if body.get("include_in_net_worth", True) else 0

    if not name or account_type not in ACCOUNT_TYPES:
        return jsonify({"error": "Invalid account."}), 400

    with closing(get_db()) as conn:
        cursor = conn.execute(
            "INSERT INTO accounts (user_id, name, type, balance, include_in_net_worth) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, account_type, float(balance), include),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"account": dict(row)}), 201


@api_bp.get("/budgets")
@api_login_required
def api_budgets():
    user_id = _current_user()["id"]
    month_key = date.today().strftime("%Y-%m")
    with closing(get_db()) as conn:
        rows = conn.execute(
            """
            SELECT b.id, b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
            FROM budgets b
            LEFT JOIN transactions t ON t.category = b.category AND t.user_id = b.user_id
                AND t.type = 'expense' AND substr(t.transaction_date, 1, 7) = ?
            WHERE b.user_id = ? GROUP BY b.id ORDER BY b.category
            """,
            (month_key, user_id),
        ).fetchall()
    return jsonify({"budgets": [dict(r) for r in rows]})


@api_bp.get("/goals")
@api_login_required
def api_goals():
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY deadline IS NULL, deadline",
            (user_id,),
        ).fetchall()
    return jsonify({"goals": [dict(r) for r in rows]})


@api_bp.get("/reports")
@api_login_required
def api_reports():
    user = _current_user()
    if not has_feature(effective_plan(user), "advanced_reports"):
        return jsonify({"error": "Plus plan required for advanced reports."}), 403

    user_id = user["id"]
    year = request.args.get("year", str(date.today().year))
    with closing(get_db()) as conn:
        monthly = conn.execute(
            """
            SELECT substr(transaction_date, 1, 7) AS month,
                   SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
                   SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expenses
            FROM transactions WHERE user_id = ? AND substr(transaction_date, 1, 4) = ?
            GROUP BY month ORDER BY month
            """,
            (user_id, year),
        ).fetchall()
        categories = conn.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM transactions WHERE user_id = ? AND type = 'expense' AND substr(transaction_date, 1, 4) = ?
            GROUP BY category ORDER BY total DESC
            """,
            (user_id, year),
        ).fetchall()
    return jsonify({
        "year": year,
        "monthly": [dict(r) for r in monthly],
        "categories": [dict(r) for r in categories],
    })


@api_bp.post("/billing/checkout")
@api_login_required
def api_checkout():
    body = request.get_json(silent=True) or {}
    plan = body.get("plan", "plus")
    if plan not in {"plus", "family"}:
        return jsonify({"error": "Invalid plan."}), 400
    user = _current_user()
    url = create_checkout_session(user["id"], user["email"], plan)
    if not url:
        return jsonify({"error": "Stripe is not configured on the server."}), 503
    return jsonify({"checkout_url": url})


@api_bp.post("/billing/portal")
@api_login_required
def api_portal():
    url = create_customer_portal(_current_user()["id"])
    if not url:
        return jsonify({"error": "No billing account found."}), 404
    return jsonify({"portal_url": url})


@api_bp.post("/billing/mobile/verify")
@api_login_required
def api_mobile_verify():
    body = request.get_json(silent=True) or {}
    ok, message = verify_mobile_purchase(_current_user()["id"], body.get("provider", ""), body)
    if not ok:
        return jsonify({"error": message}), 400
    with closing(get_db()) as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (_current_user()["id"],)).fetchone()
    return jsonify({"message": message, "user": _user_payload(user)})
