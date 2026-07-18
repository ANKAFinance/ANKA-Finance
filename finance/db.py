from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from finance.config import DB_PATH, DEFAULT_CURRENCY
from finance.plans import is_active_subscription


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if column not in {col["name"] for col in columns}:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with closing(get_db()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                subscription_status TEXT NOT NULL DEFAULT 'trial',
                currency TEXT NOT NULL DEFAULT 'USD',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                subscription_provider TEXT,
                subscription_expires_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_id INTEGER,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                transaction_date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL NOT NULL DEFAULT 0,
                include_in_net_worth INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT NOT NULL,
                monthly_limit REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL NOT NULL DEFAULT 0,
                deadline TEXT,
                notes TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL DEFAULT 'Stock',
                quantity REAL NOT NULL DEFAULT 0,
                average_price REAL NOT NULL DEFAULT 0,
                current_price REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                target_price REAL,
                notes TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mobile_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL CHECK(provider IN ('apple', 'google')),
                product_id TEXT NOT NULL,
                transaction_id TEXT NOT NULL UNIQUE,
                plan TEXT NOT NULL,
                expires_at TEXT,
                raw_payload TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bank_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bank_name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                ifsc TEXT NOT NULL,
                account_type TEXT NOT NULL DEFAULT 'savings',
                status TEXT NOT NULL DEFAULT 'pending',
                consent_id TEXT,
                consent_expires_at TEXT,
                last_synced TEXT,
                account_ref TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payment_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_account_id INTEGER,
                beneficiary_name TEXT NOT NULL,
                beneficiary_account TEXT NOT NULL,
                beneficiary_ifsc TEXT NOT NULL,
                beneficiary_upi TEXT,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                utr TEXT,
                reference TEXT,
                failure_reason TEXT,
                transfer_type TEXT NOT NULL DEFAULT 'neft',
                initiated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(from_account_id) REFERENCES accounts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS upi_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_upi_id TEXT NOT NULL,
                to_upi_id TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                txn_id TEXT,
                utr TEXT,
                qr_data TEXT,
                payer_upi TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bill_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_account_id INTEGER,
                biller_code TEXT NOT NULL,
                biller_name TEXT NOT NULL,
                consumer_number TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reference TEXT,
                bill_period TEXT,
                paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(from_account_id) REFERENCES accounts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS beneficiaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                account_number TEXT NOT NULL,
                ifsc TEXT NOT NULL,
                upi_id TEXT,
                bank_name TEXT,
                verified INTEGER NOT NULL DEFAULT 0,
                favorite INTEGER NOT NULL DEFAULT 0,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_upi_ids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                upi_id TEXT NOT NULL UNIQUE,
                bank_name TEXT NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS bill_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                biller_code TEXT NOT NULL,
                consumer_number TEXT NOT NULL,
                nickname TEXT,
                auto_pay INTEGER NOT NULL DEFAULT 0,
                remind_before_days INTEGER NOT NULL DEFAULT 3,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        for table in ["transactions", "accounts", "budgets", "goals", "investments", "watchlist"]:
            _ensure_column(conn, table, "user_id", "INTEGER")

        _ensure_column(conn, "transactions", "account_id", "INTEGER")
        _ensure_column(conn, "users", "currency", f"TEXT NOT NULL DEFAULT '{DEFAULT_CURRENCY}'")
        _ensure_column(conn, "users", "stripe_customer_id", "TEXT")
        _ensure_column(conn, "users", "stripe_subscription_id", "TEXT")
        _ensure_column(conn, "users", "subscription_provider", "TEXT")
        _ensure_column(conn, "users", "subscription_expires_at", "TEXT")

        budget_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'budgets'"
        ).fetchone()
        if budget_schema and "category TEXT NOT NULL UNIQUE" in budget_schema["sql"]:
            conn.executescript(
                """
                ALTER TABLE budgets RENAME TO budgets_old;
                CREATE TABLE budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    category TEXT NOT NULL,
                    monthly_limit REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                INSERT INTO budgets (id, user_id, category, monthly_limit)
                SELECT id, user_id, category, monthly_limit FROM budgets_old;
                DROP TABLE budgets_old;
                """
            )
        conn.commit()


def money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def user_to_dict(user: sqlite3.Row) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "plan": user["plan"],
        "subscription_status": user["subscription_status"],
        "currency": user["currency"] if "currency" in user.keys() else DEFAULT_CURRENCY,
        "subscription_provider": user["subscription_provider"] if "subscription_provider" in user.keys() else None,
        "subscription_expires_at": user["subscription_expires_at"] if "subscription_expires_at" in user.keys() else None,
    }


def effective_plan(user: sqlite3.Row) -> str:
    status = user["subscription_status"]
    plan = user["plan"]
    if plan == "free":
        return "free"
    if is_active_subscription(status):
        expires = user["subscription_expires_at"] if "subscription_expires_at" in user.keys() else None
        if expires:
            try:
                expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < datetime.now(timezone.utc):
                    return "free"
            except ValueError:
                pass
        return plan
    return "free"


def update_subscription(
    user_id: int,
    *,
    plan: str,
    status: str,
    provider: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    expires_at: str | None = None,
) -> None:
    with closing(get_db()) as conn:
        conn.execute(
            """
            UPDATE users
            SET plan = ?,
                subscription_status = ?,
                subscription_provider = ?,
                stripe_customer_id = COALESCE(?, stripe_customer_id),
                stripe_subscription_id = COALESCE(?, stripe_subscription_id),
                subscription_expires_at = ?
            WHERE id = ?
            """,
            (plan, status, provider, stripe_customer_id, stripe_subscription_id, expires_at, user_id),
        )
        conn.commit()


def delete_user_account(user_id: int) -> None:
    with closing(get_db()) as conn:
        for table in [
            "mobile_receipts",
            "transactions",
            "accounts",
            "budgets",
            "goals",
            "investments",
            "watchlist",
        ]:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
