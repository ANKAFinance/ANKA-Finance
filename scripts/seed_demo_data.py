#!/usr/bin/env python3
"""
Seed demo data for App Store / Google Play review.

Run ONCE after deploying the backend to create a demo account
with pre-loaded sample data for store reviewers to explore.

Usage:
    python scripts/seed_demo_data.py

Requires:
    - Backend running with database initialized
"""
from __future__ import annotations

import sys
from contextlib import closing
from datetime import date, timedelta

sys.path.insert(0, ".")

from finance.auth import hash_password
from finance.db import get_db


def seed() -> None:
    with closing(get_db()) as conn:
        # --- Create demo user ---
        demo_email = "demo@ankafinance.com"
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (demo_email,)).fetchone()
        if existing:
            print(f"Demo user already exists (id={existing['id']}). Cleaning and re-seeding...")
            # Delete existing demo data
            conn.execute("DELETE FROM transactions WHERE user_id = ?", (existing["id"],))
            conn.execute("DELETE FROM accounts WHERE user_id = ?", (existing["id"],))
            conn.execute("DELETE FROM budgets WHERE user_id = ?", (existing["id"],))
            conn.execute("DELETE FROM goals WHERE user_id = ?", (existing["id"],))
            conn.execute("DELETE FROM investments WHERE user_id = ?", (existing["id"],))
            conn.execute("DELETE FROM watchlist WHERE user_id = ?", (existing["id"],))
            user_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, plan, subscription_status, currency) VALUES (?, ?, ?, ?, ?, ?)",
                ("Demo User", demo_email, hash_password("DemoTest123!"), "free", "trial", "USD"),
            )
            user_id = cursor.lastrowid
            print(f"Created demo user (id={user_id})")

        # --- Create accounts ---
        accounts_data = [
            ("Checking Account", "Checking", 3420.50),
            ("Savings Account", "Savings", 12500.00),
            ("Credit Card", "Credit Card", -450.75),
            ("Emergency Fund", "Savings", 5000.00),
            ("Investment Portfolio", "Investment", 25000.00),
        ]
        account_ids = {}
        for name, acct_type, balance in accounts_data:
            cursor = conn.execute(
                "INSERT INTO accounts (user_id, name, type, balance, include_in_net_worth) VALUES (?, ?, ?, ?, 1)",
                (user_id, name, acct_type, balance),
            )
            account_ids[name] = cursor.lastrowid

        # --- Create transactions (last 3 months) ---
        categories_income = ["Salary", "Freelance", "Investments", "Gifts"]
        categories_expense = [
            "Housing", "Groceries", "Dining", "Transport", "Utilities",
            "Subscriptions", "Shopping", "Entertainment", "Healthcare",
        ]
        today = date.today()

        transactions = []
        for days_ago in range(1, 90):
            txn_date = today - timedelta(days=days_ago)
            if days_ago % 30 == 0:
                # Monthly salary
                transactions.append((user_id, account_ids["Checking Account"], "Monthly Salary", 4200.00, "Salary", "income", txn_date.isoformat(), ""))
            if days_ago % 15 == 0:
                # Freelance payment
                transactions.append((user_id, account_ids["Checking Account"], "Freelance Project", 800.00, "Freelance", "income", txn_date.isoformat(), ""))
            if days_ago % 7 == 0:
                # Weekly expenses
                transactions.append((user_id, account_ids["Credit Card"], "Grocery Store", 85.50, "Groceries", "expense", txn_date.isoformat(), ""))
                transactions.append((user_id, account_ids["Credit Card"], "Gas Station", 45.00, "Transport", "expense", txn_date.isoformat(), ""))
            if days_ago % 14 == 0:
                transactions.append((user_id, account_ids["Credit Card"], "Restaurant", 62.30, "Dining", "expense", txn_date.isoformat(), ""))
            if days_ago % 21 == 0:
                transactions.append((user_id, account_ids["Checking Account"], "Electric Bill", 95.00, "Utilities", "expense", txn_date.isoformat(), ""))
                transactions.append((user_id, account_ids["Checking Account"], "Internet", 65.00, "Utilities", "expense", txn_date.isoformat(), ""))

        # Add some specific transactions for variety
        specific_txns = [
            (user_id, account_ids["Investment Portfolio"], "Dividend Payment", 120.00, "Investments", "income", (today - timedelta(days=5)).isoformat(), ""),
            (user_id, account_ids["Checking Account"], "Birthday Gift", 100.00, "Gifts", "income", (today - timedelta(days=10)).isoformat(), ""),
            (user_id, account_ids["Credit Card"], "Netflix Subscription", 15.99, "Subscriptions", "expense", (today - timedelta(days=3)).isoformat(), ""),
            (user_id, account_ids["Credit Card"], "Amazon Purchase", 89.99, "Shopping", "expense", (today - timedelta(days=6)).isoformat(), ""),
            (user_id, account_ids["Checking Account"], "Gym Membership", 49.99, "Subscriptions", "expense", (today - timedelta(days=8)).isoformat(), ""),
            (user_id, account_ids["Credit Card"], "Movie Tickets", 24.00, "Entertainment", "expense", (today - timedelta(days=12)).isoformat(), ""),
            (user_id, account_ids["Checking Account"], "Health Insurance", 350.00, "Healthcare", "expense", (today - timedelta(days=2)).isoformat(), ""),
        ]
        transactions.extend(specific_txns)

        conn.executemany(
            "INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            transactions,
        )

        # --- Create budgets ---
        budget_data = [
            ("Groceries", 500.00),
            ("Dining", 300.00),
            ("Transport", 200.00),
            ("Shopping", 250.00),
            ("Entertainment", 150.00),
            ("Utilities", 200.00),
        ]
        for category, limit in budget_data:
            conn.execute(
                "INSERT OR IGNORE INTO budgets (user_id, category, monthly_limit) VALUES (?, ?, ?)",
                (user_id, category, limit),
            )

        # --- Create goals ---
        goals_data = [
            ("Emergency Fund", 10000.00, 5000.00, (today + timedelta(days=365)).isoformat()),
            ("Vacation to Japan", 5000.00, 1200.00, (today + timedelta(days=180)).isoformat()),
            ("New Laptop", 2000.00, 850.00, (today + timedelta(days=90)).isoformat()),
        ]
        for name, target, current, deadline in goals_data:
            conn.execute(
                "INSERT INTO goals (user_id, name, target_amount, current_amount, deadline, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, target, current, deadline, ""),
            )

        # --- Create investments ---
        holdings_data = [
            ("AAPL", "Apple Inc.", "Stock", 10, 150.00, 175.50),
            ("GOOGL", "Alphabet Inc.", "Stock", 5, 140.00, 165.30),
            ("VTI", "Vanguard Total Stock Market", "ETF", 20, 220.00, 248.75),
            ("BTC", "Bitcoin", "Cryptocurrency", 0.5, 45000.00, 52000.00),
        ]
        for symbol, name, asset_type, qty, avg_price, curr_price in holdings_data:
            conn.execute(
                "INSERT INTO investments (user_id, symbol, name, asset_type, quantity, average_price, current_price, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, symbol, name, asset_type, qty, avg_price, curr_price, ""),
            )

        # --- Create watchlist ---
        watchlist_data = [
            ("MSFT", "Microsoft Corporation", 400.00),
            ("AMZN", "Amazon.com Inc.", 180.00),
            ("ETH", "Ethereum", 3000.00),
        ]
        for symbol, name, target_price in watchlist_data:
            conn.execute(
                "INSERT INTO watchlist (user_id, symbol, name, target_price, notes) VALUES (?, ?, ?, ?, ?)",
                (user_id, symbol, name, target_price, ""),
            )

        conn.commit()

    print("✅ Demo data seeded successfully!")
    print(f"   Email:    demo@ankafinance.com")
    print(f"   Password: DemoTest123!")
    print()
    print("   The demo account includes:")
    print("   - 5 accounts with balances")
    print("   - ~50 transactions over 3 months")
    print("   - 6 budget categories")
    print("   - 3 savings goals")
    print("   - 4 investment holdings")
    print("   - 3 watchlist items")


if __name__ == "__main__":
    seed()