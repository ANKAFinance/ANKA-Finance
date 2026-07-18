from __future__ import annotations

import csv
import io
import sqlite3
from contextlib import closing
from datetime import date, datetime
from functools import wraps

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for
from flask_cors import CORS

from api.routes import api_bp
from api.banking_routes import banking_bp
from finance.auth import hash_password, verify_password
from finance.banking import (
    BILLERS,
    BILLER_CATEGORIES,
    SUPPORTED_BANKS,
    generate_upi_id,
    get_bank_statement,
    get_bill_amount,
    process_bank_transfer,
    process_bill_payment,
    process_upi_payment,
    verify_bank_account,
)
from finance.billing import (
    create_checkout_session,
    create_customer_portal,
    handle_webhook,
    stripe_enabled,
)
from finance.config import DEBUG, SECRET_KEY
from finance.currency import SUPPORTED_CURRENCIES, format_money, normalize_currency
from finance.db import effective_plan, get_db, init_db, money
from finance.plans import has_feature

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.register_blueprint(api_bp)
app.register_blueprint(banking_bp)

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Investments",
    "Gifts",
    "Other Income",
]

EXPENSE_CATEGORIES = [
    "Housing",
    "Utilities",
    "Groceries",
    "Dining",
    "Transport",
    "Healthcare",
    "Insurance",
    "Subscriptions",
    "Shopping",
    "Education",
    "Entertainment",
    "Travel",
    "Savings",
    "Other Expense",
]

ACCOUNT_TYPES = [
    "Checking",
    "Savings",
    "Credit Card",
    "Cash",
    "Investment",
    "Loan",
    "Other",
]


@app.before_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        with closing(get_db()) as conn:
            g.user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Create an account or sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def current_user_id() -> int:
    return int(g.user["id"])


def user_currency() -> str:
    if g.user and "currency" in g.user.keys():
        return normalize_currency(g.user["currency"])
    return "USD"


def require_feature(feature: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user and not has_feature(effective_plan(g.user), feature):
                flash("Upgrade to Plus to access this feature.", "error")
                return redirect(url_for("pricing"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@app.context_processor
def inject_helpers():
    effective = effective_plan(g.user) if g.user else "free"
    return {
        "income_categories": INCOME_CATEGORIES,
        "expense_categories": EXPENSE_CATEGORIES,
        "today": date.today().isoformat(),
        "account_types": ACCOUNT_TYPES,
        "current_user": g.get("user"),
        "effective_plan": effective,
        "supported_currencies": SUPPORTED_CURRENCIES,
        "user_currency": user_currency() if g.user else "USD",
        "stripe_enabled": stripe_enabled(),
    }


def fetch_dashboard_data() -> dict:
    user_id = current_user_id()
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
            """
            SELECT COALESCE(SUM(balance), 0)
            FROM accounts
            WHERE user_id = ? AND include_in_net_worth = 1
            """,
            (user_id,),
        ).fetchone()[0]
        month_key = date.today().strftime("%Y-%m")
        monthly_income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = ? AND type = 'income' AND substr(transaction_date, 1, 7) = ?
            """,
            (user_id, month_key),
        ).fetchone()[0]
        monthly_expenses = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND substr(transaction_date, 1, 7) = ?
            """,
            (user_id, month_key),
        ).fetchone()[0]
        recent_transactions = conn.execute(
            """
            SELECT t.*, a.name AS account_name
            FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.user_id = ?
            ORDER BY t.transaction_date DESC, t.id DESC
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()
        category_spending = conn.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND substr(transaction_date, 1, 7) = ?
            GROUP BY category
            ORDER BY total DESC
            LIMIT 6
            """,
            (user_id, month_key),
        ).fetchall()
        budgets = conn.execute(
            """
            SELECT b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
            FROM budgets b
            LEFT JOIN transactions t
                ON t.category = b.category
               AND t.user_id = b.user_id
               AND t.type = 'expense'
               AND substr(t.transaction_date, 1, 7) = ?
            WHERE b.user_id = ?
            GROUP BY b.id
            ORDER BY b.category
            """,
            (month_key, user_id),
        ).fetchall()
        goals = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY deadline IS NULL, deadline",
            (user_id,),
        ).fetchall()
        accounts = conn.execute(
            """
            SELECT *
            FROM accounts
            WHERE user_id = ?
            ORDER BY include_in_net_worth DESC, type, name
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()

    return {
        "total_income": money(total_income),
        "total_expenses": money(total_expenses),
        "balance": money(total_income - total_expenses),
        "net_worth": money(net_worth),
        "monthly_income": money(monthly_income),
        "monthly_expenses": money(monthly_expenses),
        "monthly_net": money(monthly_income - monthly_expenses),
        "recent_transactions": recent_transactions,
        "category_spending": category_spending,
        "budgets": budgets,
        "goals": goals,
        "accounts": accounts,
    }


@app.route("/welcome")
def welcome():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("welcome.html")


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        currency = normalize_currency(request.form.get("currency"))

        if not name or "@" not in email or len(password) < 8:
            flash("Use your name, a valid email, and a password with at least 8 characters.", "error")
        else:
            try:
                with closing(get_db()) as conn:
                    cursor = conn.execute(
                        """
                        INSERT INTO users (name, email, password_hash, currency)
                        VALUES (?, ?, ?, ?)
                        """,
                        (name, email, hash_password(password), currency),
                    )
                    conn.commit()
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                flash("Welcome. Your finance workspace is ready.", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")

    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with closing(get_db()) as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and verify_password(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Signed in.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Email or password is incorrect.", "error")

    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("welcome"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        currency = normalize_currency(request.form.get("currency"))
        if not name:
            flash("Name cannot be empty.", "error")
        else:
            with closing(get_db()) as conn:
                conn.execute(
                    "UPDATE users SET name = ?, currency = ? WHERE id = ?",
                    (name, currency, current_user_id()),
                )
                conn.commit()
            flash("Settings updated.", "success")
            return redirect(url_for("settings"))
    return render_template("settings.html")


@app.route("/billing/checkout/<plan>")
@login_required
def billing_checkout(plan: str):
    if plan not in {"plus", "family"}:
        flash("Invalid plan.", "error")
        return redirect(url_for("pricing"))
    url = create_checkout_session(current_user_id(), g.user["email"], plan)
    if not url:
        flash("Payments are not configured yet. Add Stripe keys to your environment.", "error")
        return redirect(url_for("pricing"))
    return redirect(url)


@app.route("/billing/portal")
@login_required
def billing_portal():
    url = create_customer_portal(current_user_id())
    if not url:
        flash("No active subscription found.", "error")
        return redirect(url_for("settings"))
    return redirect(url)


@app.route("/billing/success")
@login_required
def billing_success():
    flash("Subscription activated. Welcome to your new plan.", "success")
    return redirect(url_for("dashboard"))


@app.route("/billing/webhook", methods=["POST"])
def billing_webhook():
    ok, message = handle_webhook(
        request.get_data(),
        request.headers.get("Stripe-Signature", ""),
    )
    if not ok:
        return {"error": message}, 400
    return {"status": message}, 200


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", **fetch_dashboard_data())


@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    user_id = current_user_id()
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        amount = request.form.get("amount", type=float)
        category = request.form.get("category", "").strip()
        txn_type = request.form.get("type", "expense")
        account_id = request.form.get("account_id", type=int)
        transaction_date = request.form.get("transaction_date") or date.today().isoformat()
        notes = request.form.get("notes", "").strip()

        if not description or not amount or amount <= 0 or txn_type not in {"income", "expense"}:
            flash("Please enter a valid transaction.", "error")
        else:
            with closing(get_db()) as conn:
                conn.execute(
                    """
                    INSERT INTO transactions
                        (user_id, account_id, description, amount, category, type, transaction_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, account_id, description, amount, category, txn_type, transaction_date, notes),
                )
                conn.commit()
            flash("Transaction added.", "success")
        return redirect(url_for("transactions"))

    selected_type = request.args.get("type", "all")
    selected_category = request.args.get("category", "all")
    search = request.args.get("search", "").strip()

    query = """
        SELECT t.*, a.name AS account_name
        FROM transactions t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.user_id = ?
    """
    params: list[str | int] = [user_id]
    if selected_type in {"income", "expense"}:
        query += " AND t.type = ?"
        params.append(selected_type)
    if selected_category != "all":
        query += " AND t.category = ?"
        params.append(selected_category)
    if search:
        query += " AND (t.description LIKE ? OR t.notes LIKE ? OR a.name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY t.transaction_date DESC, t.id DESC"

    with closing(get_db()) as conn:
        rows = conn.execute(query, params).fetchall()
        accounts = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY name",
            (user_id,),
        ).fetchall()

    return render_template(
        "transactions.html",
        transactions=rows,
        accounts=accounts,
        selected_type=selected_type,
        selected_category=selected_category,
        search=search,
    )


@app.route("/accounts", methods=["GET", "POST"])
@login_required
def accounts():
    user_id = current_user_id()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        account_type = request.form.get("type", "Checking")
        balance = request.form.get("balance", type=float)
        include = 1 if request.form.get("include_in_net_worth") == "on" else 0

        if not name or account_type not in ACCOUNT_TYPES or balance is None:
            flash("Please enter a valid account.", "error")
        else:
            with closing(get_db()) as conn:
                conn.execute(
                    """
                    INSERT INTO accounts (user_id, name, type, balance, include_in_net_worth)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, name, account_type, balance, include),
                )
                conn.commit()
            flash("Account added.", "success")
        return redirect(url_for("accounts"))

    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY type, name",
            (user_id,),
        ).fetchall()
        net_worth = conn.execute(
            """
            SELECT COALESCE(SUM(balance), 0)
            FROM accounts
            WHERE user_id = ? AND include_in_net_worth = 1
            """,
            (user_id,),
        ).fetchone()[0]
    return render_template("accounts.html", accounts=rows, net_worth=money(net_worth))


@app.route("/investments", methods=["GET", "POST"])
@login_required
@require_feature("investments")
def investments():
    user_id = current_user_id()
    if request.method == "POST":
        form_type = request.form.get("form_type", "holding")
        symbol = request.form.get("symbol", "").strip().upper()
        name = request.form.get("name", "").strip()
        notes = request.form.get("notes", "").strip()

        if form_type == "watchlist":
            target_price = request.form.get("target_price", type=float)
            if not symbol or not name:
                flash("Enter a valid watchlist item.", "error")
            else:
                with closing(get_db()) as conn:
                    conn.execute(
                        """
                        INSERT INTO watchlist (user_id, symbol, name, target_price, notes)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, symbol, name, target_price, notes),
                    )
                    conn.commit()
                flash("Watchlist item added.", "success")
        else:
            asset_type = request.form.get("asset_type", "Stock")
            quantity = request.form.get("quantity", type=float)
            average_price = request.form.get("average_price", type=float)
            current_price = request.form.get("current_price", type=float)
            if not symbol or not name or quantity is None or average_price is None or current_price is None:
                flash("Enter a valid investment holding.", "error")
            else:
                with closing(get_db()) as conn:
                    conn.execute(
                        """
                        INSERT INTO investments
                            (user_id, symbol, name, asset_type, quantity, average_price, current_price, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, symbol, name, asset_type, quantity, average_price, current_price, notes),
                    )
                    conn.commit()
                flash("Holding added.", "success")
        return redirect(url_for("investments"))

    with closing(get_db()) as conn:
        holdings = conn.execute(
            "SELECT * FROM investments WHERE user_id = ? ORDER BY symbol",
            (user_id,),
        ).fetchall()
        watch_items = conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY symbol",
            (user_id,),
        ).fetchall()

    total_value = sum(row["quantity"] * row["current_price"] for row in holdings)
    total_cost = sum(row["quantity"] * row["average_price"] for row in holdings)
    total_gain = total_value - total_cost
    allocation = []
    for row in holdings:
        value = row["quantity"] * row["current_price"]
        allocation.append(
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "value": value,
                "weight": (value / total_value * 100) if total_value else 0,
            }
        )

    return render_template(
        "investments.html",
        holdings=holdings,
        watch_items=watch_items,
        total_value=money(total_value),
        total_cost=money(total_cost),
        total_gain=money(total_gain),
        total_gain_percent=money((total_gain / total_cost * 100) if total_cost else 0),
        allocation=allocation,
    )


@app.route("/investments/<int:investment_id>/delete", methods=["POST"])
@login_required
@require_feature("investments")
def delete_investment(investment_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM investments WHERE id = ? AND user_id = ?",
            (investment_id, current_user_id()),
        )
        conn.commit()
    flash("Holding removed.", "success")
    return redirect(url_for("investments"))


@app.route("/watchlist/<int:item_id>/delete", methods=["POST"])
@login_required
@require_feature("investments")
def delete_watchlist_item(item_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE id = ? AND user_id = ?",
            (item_id, current_user_id()),
        )
        conn.commit()
    flash("Watchlist item removed.", "success")
    return redirect(url_for("investments"))


@app.route("/accounts/<int:account_id>/update", methods=["POST"])
@login_required
def update_account(account_id: int):
    balance = request.form.get("balance", type=float)
    include = 1 if request.form.get("include_in_net_worth") == "on" else 0
    if balance is None:
        flash("Enter a valid balance.", "error")
    else:
        with closing(get_db()) as conn:
            conn.execute(
                """
                UPDATE accounts
                SET balance = ?, include_in_net_worth = ?
                WHERE id = ? AND user_id = ?
                """,
                (balance, include, account_id, current_user_id()),
            )
            conn.commit()
        flash("Account updated.", "success")
    return redirect(url_for("accounts"))


@app.route("/accounts/<int:account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, current_user_id()),
        )
        conn.commit()
    flash("Account removed.", "success")
    return redirect(url_for("accounts"))


@app.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (transaction_id, current_user_id()),
        )
        conn.commit()
    flash("Transaction deleted.", "success")
    return redirect(url_for("transactions"))


@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    user_id = current_user_id()
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        monthly_limit = request.form.get("monthly_limit", type=float)
        if not category or not monthly_limit or monthly_limit <= 0:
            flash("Please enter a valid budget.", "error")
        else:
            with closing(get_db()) as conn:
                existing = conn.execute(
                    "SELECT id FROM budgets WHERE user_id = ? AND category = ?",
                    (user_id, category),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE budgets SET monthly_limit = ? WHERE id = ? AND user_id = ?",
                        (monthly_limit, existing["id"], user_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO budgets (user_id, category, monthly_limit) VALUES (?, ?, ?)",
                        (user_id, category, monthly_limit),
                    )
                conn.commit()
            flash("Budget saved.", "success")
        return redirect(url_for("budgets"))

    month_key = request.args.get("month", date.today().strftime("%Y-%m"))
    with closing(get_db()) as conn:
        rows = conn.execute(
            """
            SELECT b.id, b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
            FROM budgets b
            LEFT JOIN transactions t
                ON t.category = b.category
               AND t.user_id = b.user_id
               AND t.type = 'expense'
               AND substr(t.transaction_date, 1, 7) = ?
            WHERE b.user_id = ?
            GROUP BY b.id
            ORDER BY b.category
            """,
            (month_key, user_id),
        ).fetchall()

    return render_template("budgets.html", budgets=rows, month_key=month_key)


@app.route("/budgets/<int:budget_id>/delete", methods=["POST"])
@login_required
def delete_budget(budget_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, current_user_id()),
        )
        conn.commit()
    flash("Budget removed.", "success")
    return redirect(url_for("budgets"))


@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    user_id = current_user_id()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        target_amount = request.form.get("target_amount", type=float)
        current_amount = request.form.get("current_amount", type=float) or 0
        deadline = request.form.get("deadline") or None
        notes = request.form.get("notes", "").strip()

        if not name or not target_amount or target_amount <= 0 or current_amount < 0:
            flash("Please enter a valid goal.", "error")
        else:
            with closing(get_db()) as conn:
                conn.execute(
                    """
                    INSERT INTO goals (user_id, name, target_amount, current_amount, deadline, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, name, target_amount, current_amount, deadline, notes),
                )
                conn.commit()
            flash("Goal added.", "success")
        return redirect(url_for("goals"))

    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM goals WHERE user_id = ? ORDER BY deadline IS NULL, deadline",
            (user_id,),
        ).fetchall()
    return render_template("goals.html", goals=rows)


@app.route("/goals/<int:goal_id>/update", methods=["POST"])
@login_required
def update_goal(goal_id: int):
    current_amount = request.form.get("current_amount", type=float)
    if current_amount is None or current_amount < 0:
        flash("Enter a valid saved amount.", "error")
    else:
        with closing(get_db()) as conn:
            conn.execute(
                "UPDATE goals SET current_amount = ? WHERE id = ? AND user_id = ?",
                (current_amount, goal_id, current_user_id()),
            )
            conn.commit()
        flash("Goal progress updated.", "success")
    return redirect(url_for("goals"))


@app.route("/goals/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete_goal(goal_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, current_user_id()),
        )
        conn.commit()
    flash("Goal removed.", "success")
    return redirect(url_for("goals"))


@app.route("/reports")
@login_required
@require_feature("advanced_reports")
def reports():
    user_id = current_user_id()
    year = request.args.get("year", str(date.today().year))
    with closing(get_db()) as conn:
        monthly = conn.execute(
            """
            SELECT substr(transaction_date, 1, 7) AS month,
                   SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
                   SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expenses
            FROM transactions
            WHERE user_id = ? AND substr(transaction_date, 1, 4) = ?
            GROUP BY month
            ORDER BY month
            """,
            (user_id, year),
        ).fetchall()
        categories = conn.execute(
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND substr(transaction_date, 1, 4) = ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, year),
        ).fetchall()
        years = conn.execute(
            """
            SELECT DISTINCT substr(transaction_date, 1, 4) AS year
            FROM transactions
            WHERE user_id = ?
            ORDER BY year DESC
            """,
            (user_id,),
        ).fetchall()

    return render_template(
        "reports.html",
        year=year,
        years=[row["year"] for row in years] or [year],
        monthly=monthly,
        categories=categories,
    )


@app.route("/export/transactions.csv")
@login_required
def export_transactions():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "description", "type", "category", "account", "amount", "notes"])
    with closing(get_db()) as conn:
        rows = conn.execute(
            """
            SELECT t.transaction_date, t.description, t.type, t.category,
                   COALESCE(a.name, '') AS account_name, t.amount, t.notes
            FROM transactions t
            LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.user_id = ?
            ORDER BY t.transaction_date DESC, t.id DESC
            """,
            (current_user_id(),),
        ).fetchall()
    for row in rows:
        writer.writerow(
            [
                row["transaction_date"],
                row["description"],
                row["type"],
                row["category"],
                row["account_name"],
                row["amount"],
                row["notes"],
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


# ============================================================================
# BANKING WEB ROUTES
# ============================================================================


@app.route("/banking")
@login_required
def banking_home():
    """Banking home page — like Google Pay/PhonePe main screen."""
    user_id = current_user_id()
    with closing(get_db()) as conn:
        connections = conn.execute(
            "SELECT bc.*, a.balance FROM bank_connections bc LEFT JOIN accounts a ON a.user_id = bc.user_id AND a.name LIKE bc.bank_name || '%' WHERE bc.user_id = ? AND bc.status = 'active'",
            (user_id,),
        ).fetchall()
        accounts = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY balance DESC",
            (user_id,),
        ).fetchall()
        upi_ids = conn.execute(
            "SELECT * FROM user_upi_ids WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        recent_txns = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY transaction_date DESC, id DESC LIMIT 10",
            (user_id,),
        ).fetchall()

    total_balance = sum(money(a["balance"]) for a in accounts)
    recent_activity = []
    for t in recent_txns:
        recent_activity.append({
            "description": t["description"],
            "amount": t["amount"],
            "type": t["type"],
            "date": t["transaction_date"],
            "icon": "💳" if t["type"] == "expense" else "💰",
        })

    return render_template(
        "banking.html",
        connections=connections,
        accounts=accounts,
        upi_ids=upi_ids,
        total_balance=total_balance,
        recent_activity=recent_activity,
    )


@app.route("/banking/connect", methods=["GET", "POST"])
@login_required
def banking_connect():
    """Connect a real bank account."""
    user_id = current_user_id()
    if request.method == "POST":
        bank_name = request.form.get("bank_name", "").strip()
        account_number = request.form.get("account_number", "").strip()
        ifsc = request.form.get("ifsc", "").strip()
        account_type = request.form.get("account_type", "savings")

        if not bank_name or not account_number:
            flash("Bank name and account number are required.", "error")
            return redirect(url_for("banking_connect"))

        # Simulate bank connection via Account Aggregator
        from finance.banking import create_account_aggregator_consent, fetch_account_aggregator_data, generate_upi_id
        consent = create_account_aggregator_consent(user_id, bank_name)
        bank_data = fetch_account_aggregator_data(consent["consent_id"], bank_name)
        acct = bank_data["account"]
        transactions = bank_data["transactions"]

        with closing(get_db()) as conn:
            # Insert bank connection
            conn.execute(
                "INSERT INTO bank_connections (user_id, bank_name, account_number, ifsc, account_type, status, consent_id, consent_expires_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (user_id, bank_name, acct["account_number"], acct["ifsc"], account_type, consent["consent_id"], consent["expires_at"]),
            )

            # Create/update account
            existing = conn.execute("SELECT id FROM accounts WHERE user_id = ? AND name = ?", (user_id, f"{bank_name} {account_type}")).fetchone()
            if existing:
                conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (money(acct["current_balance"]), existing["id"]))
                account_id = existing["id"]
            else:
                cursor = conn.execute("INSERT INTO accounts (user_id, name, type, balance, include_in_net_worth) VALUES (?, ?, ?, ?, 1)", (user_id, f"{bank_name} {account_type}", "Checking", money(acct["current_balance"])))
                account_id = cursor.lastrowid

            # Create UPI ID
            upi_id = generate_upi_id(g.user["name"], bank_name)
            existing_upi = conn.execute("SELECT id FROM user_upi_ids WHERE user_id = ? AND upi_id = ?", (user_id, upi_id)).fetchone()
            if not existing_upi:
                is_primary = 0 if conn.execute("SELECT id FROM user_upi_ids WHERE user_id = ? AND is_primary = 1", (user_id,)).fetchone() else 1
                conn.execute("INSERT INTO user_upi_ids (user_id, upi_id, bank_name, is_primary) VALUES (?, ?, ?, ?)", (user_id, upi_id, bank_name, is_primary))

            # Import transactions
            for txn in transactions:
                txn_type = "income" if txn["type"] == "credit" else "expense"
                conn.execute("INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, account_id, txn["description"], money(txn["amount"]), "Bank Transfer", txn_type, txn["date"], f"Auto-synced from {bank_name}"))
            conn.commit()

        flash(f"✓ {bank_name} account linked! {len(transactions)} transactions imported. UPI ID: {upi_id}", "success")
        return redirect(url_for("banking_home"))

    return render_template("banking_connect.html", supported_banks=SUPPORTED_BANKS)


@app.route("/banking/transfer", methods=["GET", "POST"])
@login_required
def banking_transfer():
    """Send money via bank transfer or UPI."""
    user_id = current_user_id()
    if request.method == "POST":
        mode = request.form.get("mode", "bank")
        amount = request.form.get("amount", type=float)

        if mode == "bank":
            from_account_id = request.form.get("from_account_id", type=int)
            beneficiary_id = request.form.get("beneficiary_id", type=int)
            beneficiary_name = request.form.get("beneficiary_name", "").strip()
            beneficiary_account = request.form.get("beneficiary_account", "").strip()
            beneficiary_ifsc = request.form.get("beneficiary_ifsc", "").strip()
            reference = request.form.get("reference", "").strip()

            if beneficiary_id:
                with closing(get_db()) as conn:
                    ben = conn.execute("SELECT * FROM beneficiaries WHERE id = ? AND user_id = ?", (beneficiary_id, user_id)).fetchone()
                    if ben:
                        beneficiary_name = ben["name"]
                        beneficiary_account = ben["account_number"]
                        beneficiary_ifsc = ben["ifsc"]

            success, msg, data = process_bank_transfer(user_id, from_account_id, beneficiary_name, beneficiary_account, beneficiary_ifsc, amount, reference)
            if not success:
                flash(msg, "error")
                return redirect(url_for("banking_transfer"))

            with closing(get_db()) as conn:
                conn.execute("INSERT INTO payment_transfers (user_id, from_account_id, beneficiary_name, beneficiary_account, beneficiary_ifsc, amount, status, utr, reference) VALUES (?, ?, ?, ?, ?, ?, 'success', ?, ?)",
                    (user_id, from_account_id, beneficiary_name, beneficiary_account, beneficiary_ifsc, money(amount), data["utr"], data["reference"]))
                conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?", (money(amount), from_account_id, user_id))
                conn.execute("INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, from_account_id, f"Transfer to {beneficiary_name}", money(amount), "Bank Transfer", "expense", date.today().isoformat(), f"UTR: {data['utr']}"))
                conn.commit()
            flash(msg, "success")

        elif mode == "upi":
            from_upi_id = request.form.get("from_upi_id", "").strip()
            to_upi_id = request.form.get("to_upi_id", "").strip()
            note = request.form.get("note", "").strip()

            success, msg, data = process_upi_payment(user_id, from_upi_id, to_upi_id, amount, note)
            if not success:
                flash(msg, "error")
                return redirect(url_for("banking_transfer"))

            with closing(get_db()) as conn:
                conn.execute("INSERT INTO upi_payments (user_id, from_upi_id, to_upi_id, amount, note, status, txn_id, utr) VALUES (?, ?, ?, ?, ?, 'success', ?, ?)",
                    (user_id, from_upi_id, to_upi_id, money(amount), note, data["txn_id"], data["utr"]))
                conn.commit()
            flash(msg, "success")

        return redirect(url_for("banking_home"))

    with closing(get_db()) as conn:
        accounts = conn.execute("SELECT * FROM accounts WHERE user_id = ? ORDER BY balance DESC", (user_id,)).fetchall()
        beneficiaries = conn.execute("SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY favorite DESC, name", (user_id,)).fetchall()
        upi_ids = conn.execute("SELECT * FROM user_upi_ids WHERE user_id = ?", (user_id,)).fetchall()

    return render_template("banking_transfer.html", accounts=accounts, beneficiaries=beneficiaries, upi_ids=upi_ids)


@app.route("/banking/bills", methods=["GET", "POST"])
@login_required
def banking_bills():
    """Pay bills and recharge."""
    user_id = current_user_id()
    selected_category = request.args.get("category", "electricity")

    if request.method == "POST":
        biller_code = request.form.get("biller_code", "").strip()
        biller_name = request.form.get("biller_name", "").strip()
        consumer_number = request.form.get("consumer_number", "").strip()
        amount = request.form.get("amount", type=float)
        from_account_id = request.form.get("from_account_id", type=int)

        success, msg, data = process_bill_payment(biller_code, consumer_number, amount, user_id, from_account_id)
        if not success:
            flash(msg, "error")
            return redirect(url_for("banking_bills", category=selected_category))

        with closing(get_db()) as conn:
            conn.execute("INSERT INTO bill_payments (user_id, from_account_id, biller_code, biller_name, consumer_number, amount, status, reference) VALUES (?, ?, ?, ?, ?, ?, 'success', ?)",
                (user_id, from_account_id, biller_code, biller_name, consumer_number, money(amount), data["reference"]))
            conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?", (money(amount), from_account_id, user_id))
            conn.execute("INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, from_account_id, f"Bill Payment - {biller_name}", money(amount), "Bills", "expense", date.today().isoformat(), f"Ref: {data['reference']}"))
            conn.commit()
        flash(msg, "success")
        return redirect(url_for("banking_home"))

    billers = BILLERS.get(selected_category, [])
    with closing(get_db()) as conn:
        accounts = conn.execute("SELECT * FROM accounts WHERE user_id = ? ORDER BY balance DESC", (user_id,)).fetchall()
        recent_bills = conn.execute("SELECT * FROM bill_payments WHERE user_id = ? ORDER BY paid_at DESC LIMIT 10", (user_id,)).fetchall()

    return render_template("banking_bills.html",
        biller_categories=BILLER_CATEGORIES,
        selected_category=selected_category,
        billers=billers,
        accounts=accounts,
        recent_bills=recent_bills,
    )


@app.route("/banking/beneficiaries", methods=["GET", "POST"])
@login_required
def banking_beneficiaries():
    """Manage beneficiaries."""
    user_id = current_user_id()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        account_number = request.form.get("account_number", "").strip()
        ifsc = request.form.get("ifsc", "").strip()
        upi_id = request.form.get("upi_id", "").strip()
        bank_name = request.form.get("bank_name", "").strip()

        if not name or (not account_number and not upi_id):
            flash("Name and account/UPI ID required.", "error")
        else:
            verified = 0
            if account_number and ifsc:
                is_valid, holder = verify_bank_account(account_number, ifsc)
                verified = 1 if is_valid else 0
            with closing(get_db()) as conn:
                conn.execute("INSERT INTO beneficiaries (user_id, name, account_number, ifsc, upi_id, bank_name, verified) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, name, account_number, ifsc, upi_id, bank_name, verified))
                conn.commit()
            flash(f"Beneficiary '{name}' added.", "success")
        return redirect(url_for("banking_beneficiaries"))

    with closing(get_db()) as conn:
        beneficiaries = conn.execute("SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY favorite DESC, name", (user_id,)).fetchall()
    return render_template("banking_beneficiaries.html", beneficiaries=beneficiaries)


@app.route("/banking/qr")
@login_required
def banking_qr():
    """Show UPI QR code for receiving payments."""
    with closing(get_db()) as conn:
        upi_ids = conn.execute("SELECT * FROM user_upi_ids WHERE user_id = ?", (current_user_id(),)).fetchall()
    return render_template("banking_qr.html", upi_ids=upi_ids)


@app.route("/banking/history")
@login_required
def banking_history():
    """Full banking history."""
    user_id = current_user_id()
    with closing(get_db()) as conn:
        transfers = conn.execute("SELECT * FROM payment_transfers WHERE user_id = ? ORDER BY initiated_at DESC LIMIT 50", (user_id,)).fetchall()
        upi_payments = conn.execute("SELECT * FROM upi_payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,)).fetchall()
        bills = conn.execute("SELECT * FROM bill_payments WHERE user_id = ? ORDER BY paid_at DESC LIMIT 50", (user_id,)).fetchall()
    return render_template("banking_history.html", transfers=transfers, upi_payments=upi_payments, bills=bills)


@app.route("/banking/connections/<int:connection_id>/sync", methods=["POST"])
@login_required
def banking_sync(connection_id: int):
    """Sync a bank connection."""
    user_id = current_user_id()
    with closing(get_db()) as conn:
        connection = conn.execute("SELECT * FROM bank_connections WHERE id = ? AND user_id = ?", (connection_id, user_id)).fetchone()
        if not connection:
            flash("Connection not found.", "error")
            return redirect(url_for("banking_home"))
        account = conn.execute("SELECT id FROM accounts WHERE user_id = ? AND name LIKE ?", (user_id, f"{connection['bank_name']}%")).fetchone()

    new_txns = get_bank_statement(connection["bank_name"], connection["account_number"], 10)
    imported = 0
    with closing(get_db()) as conn:
        for txn in new_txns:
            txn_type = "income" if txn["type"] == "credit" else "expense"
            existing = conn.execute("SELECT id FROM transactions WHERE user_id = ? AND description = ? AND amount = ? AND transaction_date = ?",
                (user_id, txn["description"], money(txn["amount"]), txn["date"])).fetchone()
            if not existing and account:
                conn.execute("INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, account["id"], txn["description"], money(txn["amount"]), "Bank Transfer", txn_type, txn["date"], f"Synced from {connection['bank_name']}"))
                imported += 1
        conn.execute("UPDATE bank_connections SET last_synced = CURRENT_TIMESTAMP WHERE id = ?", (connection_id,))
        conn.commit()

    flash(f"Synced {imported} new transactions from {connection['bank_name']}.", "success")
    return redirect(url_for("banking_home"))


@app.route("/banking/connections/<int:connection_id>/disconnect", methods=["POST"])
@login_required
def banking_disconnect(connection_id: int):
    """Disconnect a bank."""
    with closing(get_db()) as conn:
        conn.execute("DELETE FROM bank_connections WHERE id = ? AND user_id = ?", (connection_id, current_user_id()))
        conn.commit()
    flash("Bank account disconnected.", "success")
    return redirect(url_for("banking_home"))


@app.template_filter("currency")
def currency(value: float | int | None) -> str:
    return format_money(value, user_currency() if g.user else "USD")


@app.template_filter("percent")
def percent(value: float | int | None) -> str:
    return f"{money(value)}%"


@app.template_filter("datefmt")
def datefmt(value: str | None) -> str:
    if not value:
        return "No deadline"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return value


if __name__ == "__main__":
    init_db()
    app.run(debug=DEBUG)