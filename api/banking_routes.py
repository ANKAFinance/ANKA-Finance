"""Banking API routes — bank linking, UPI, transfers, bills, beneficiaries."""

from __future__ import annotations

import json
from contextlib import closing
from datetime import date, datetime

from flask import Blueprint, g, jsonify, request

from finance.auth import api_login_required
from finance.banking import (
    BILLERS,
    SUPPORTED_BANKS,
    BankConnection,
    ConnectionStatus,
    PaymentStatus,
    TransactionType,
    create_account_aggregator_consent,
    fetch_account_aggregator_data,
    generate_account_number,
    generate_ifsc,
    generate_qr_upi_string,
    generate_upi_id,
    get_bank_statement,
    get_bill_amount,
    get_ifsc_details,
    process_bank_transfer,
    process_bill_payment,
    process_upi_payment,
    search_banks,
    search_branches,
    update_account_balance,
)
from finance.config import APP_URL
from finance.db import get_db, money

banking_bp = Blueprint("banking_api", __name__, url_prefix="/api/v1/banking")


def _current_user():
    return g.api_user


# ---------------------------------------------------------------------------
# Bank discovery & IFSC lookup
# ---------------------------------------------------------------------------


@banking_bp.get("/banks")
def api_banks():
    """List all supported banks."""
    query = request.args.get("q", "").strip()
    if query:
        results = search_banks(query)
    else:
        results = [{"name": b, "logo": b[:2].upper()} for b in SUPPORTED_BANKS]
    return jsonify({"banks": results})


@banking_bp.get("/banks/<bank_name>/branches")
def api_bank_branches(bank_name: str):
    """Get branches for a bank."""
    city = request.args.get("city", "").strip()
    branches = search_branches(bank_name, city)
    return jsonify({"branches": branches})


@banking_bp.get("/ifsc/<ifsc>")
def api_ifsc_lookup(ifsc: str):
    """Look up IFSC code details."""
    details = get_ifsc_details(ifsc.upper())
    if not details:
        return jsonify({"error": "IFSC code not found."}), 404
    return jsonify({"ifsc": details})


@banking_bp.post("/verify-account")
def api_verify_account():
    """Verify a bank account (name lookup)."""
    body = request.get_json(silent=True) or {}
    account_number = (body.get("account_number") or "").strip()
    ifsc = (body.get("ifsc") or "").strip()

    from finance.banking import verify_bank_account
    is_valid, holder_name = verify_bank_account(account_number, ifsc)
    if not is_valid:
        return jsonify({"error": "Account verification failed.", "verified": False}), 400
    return jsonify({"verified": True, "account_holder": holder_name})


# ---------------------------------------------------------------------------
# Connect real bank account (Account Aggregator flow)
# ---------------------------------------------------------------------------


@banking_bp.post("/connect")
@api_login_required
def api_connect_bank():
    """Initiate bank account connection via Account Aggregator."""
    user = _current_user()
    body = request.get_json(silent=True) or {}
    bank_name = (body.get("bank_name") or "").strip()
    account_number = (body.get("account_number") or "").strip()
    ifsc = (body.get("ifsc") or "").strip()

    if not bank_name or not account_number:
        return jsonify({"error": "Bank name and account number are required."}), 400

    if bank_name not in SUPPORTED_BANKS:
        return jsonify({"error": f"Bank '{bank_name}' is not supported. Supported: {', '.join(SUPPORTED_BANKS)}"}), 400

    # Create Account Aggregator consent
    consent = create_account_aggregator_consent(user["id"], bank_name)

    # Fetch bank data (simulated)
    bank_data = fetch_account_aggregator_data(consent["consent_id"], bank_name)
    account = bank_data["account"]
    transactions = bank_data["transactions"]

    # Create the linked account
    with closing(get_db()) as conn:
        # Insert bank connection
        cursor = conn.execute(
            """
            INSERT INTO bank_connections (user_id, bank_name, account_number, ifsc, account_type, status, consent_id, consent_expires_at, account_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"], bank_name, account["account_number"], account["ifsc"],
                account["account_type"], ConnectionStatus.ACTIVE.value,
                consent["consent_id"], consent["expires_at"], account.get("account_ref"),
            ),
        )
        connection_id = cursor.lastrowid

        # Update the existing account or create a linked one
        existing_account = conn.execute(
            "SELECT id FROM accounts WHERE user_id = ? AND name = ?",
            (user["id"], f"{bank_name} - {account['account_type']}"),
        ).fetchone()

        if existing_account:
            conn.execute(
                "UPDATE accounts SET balance = ? WHERE id = ? AND user_id = ?",
                (money(account["current_balance"]), existing_account["id"], user["id"]),
            )
            account_id = existing_account["id"]
        else:
            cursor2 = conn.execute(
                """
                INSERT INTO accounts (user_id, name, type, balance, include_in_net_worth)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user["id"], f"{bank_name} {account['account_type']}", "Checking",
                 money(account["current_balance"]), 1),
            )
            account_id = cursor2.lastrowid

        # Create a UPI ID for this account
        upi_id = generate_upi_id(user["name"], bank_name)
        existing_upi = conn.execute(
            "SELECT id FROM user_upi_ids WHERE user_id = ? AND upi_id = ?",
            (user["id"], upi_id),
        ).fetchone()
        if not existing_upi:
            is_primary = 1 if not conn.execute(
                "SELECT id FROM user_upi_ids WHERE user_id = ? AND is_primary = 1",
                (user["id"],),
            ).fetchone() else 0
            conn.execute(
                "INSERT INTO user_upi_ids (user_id, upi_id, bank_name, is_primary) VALUES (?, ?, ?, ?)",
                (user["id"], upi_id, bank_name, is_primary),
            )

        # Import transactions from bank statement
        for txn in transactions:
            txn_type = "income" if txn["type"] == "credit" else "expense"
            conn.execute(
                """
                INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], account_id, txn["description"], money(txn["amount"]),
                 "Bank Transfer", txn_type, txn["date"],
                 f"Auto-synced from {bank_name} | {txn.get('balance', '')}"),
            )

        conn.commit()

        # Fetch updated accounts
        accounts = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY type, name",
            (user["id"],),
        ).fetchall()
        upi_ids = conn.execute(
            "SELECT * FROM user_upi_ids WHERE user_id = ?",
            (user["id"],),
        ).fetchall()

    return jsonify({
        "connection_id": connection_id,
        "account_id": account_id,
        "consent": consent,
        "account": dict(accounts[-1]) if accounts else None,
        "transactions_imported": len(transactions),
        "upi_id": upi_id,
        "message": f"✓ {bank_name} account linked! {len(transactions)} transactions imported.",
    }), 201


@banking_bp.get("/connections")
@api_login_required
def api_bank_connections():
    """List all bank connections for the user."""
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        connections = conn.execute(
            "SELECT * FROM bank_connections WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        upi_ids = conn.execute(
            "SELECT * FROM user_upi_ids WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return jsonify({
        "connections": [dict(c) for c in connections],
        "upi_ids": [dict(u) for u in upi_ids],
    })


@banking_bp.get("/connections/<int:connection_id>/sync")
@api_login_required
def api_sync_bank(connection_id: int):
    """Sync latest transactions from a connected bank."""
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        connection = conn.execute(
            "SELECT * FROM bank_connections WHERE id = ? AND user_id = ?",
            (connection_id, user_id),
        ).fetchone()
        if not connection:
            return jsonify({"error": "Connection not found."}), 404

        account = conn.execute(
            "SELECT id FROM accounts WHERE user_id = ? AND name LIKE ?",
            (user_id, f"{connection['bank_name']}%"),
        ).fetchone()

    # Fetch latest transactions
    new_txns = get_bank_statement(connection["bank_name"], connection["account_number"], 10)
    imported = 0
    updated_balance = connection["balance"] if "balance" in connection.keys() else 0

    if new_txns:
        updated_balance = new_txns[0].get("balance", updated_balance)

    with closing(get_db()) as conn:
        if account:
            conn.execute(
                "UPDATE accounts SET balance = ? WHERE id = ? AND user_id = ?",
                (money(updated_balance), account["id"], user_id),
            )

        for txn in new_txns:
            txn_type = "income" if txn["type"] == "credit" else "expense"
            # Avoid duplicates
            existing = conn.execute(
                "SELECT id FROM transactions WHERE user_id = ? AND description = ? AND amount = ? AND transaction_date = ?",
                (user_id, txn["description"], money(txn["amount"]), txn["date"]),
            ).fetchone()
            if not existing and account:
                conn.execute(
                    """
                    INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, account["id"], txn["description"], money(txn["amount"]),
                     "Bank Transfer", txn_type, txn["date"],
                     f"Synced from {connection['bank_name']}"),
                )
                imported += 1

        conn.execute(
            "UPDATE bank_connections SET last_synced = CURRENT_TIMESTAMP WHERE id = ?",
            (connection_id,),
        )
        conn.commit()

    return jsonify({
        "synced": imported,
        "new_balance": money(updated_balance),
        "message": f"Synced {imported} new transactions. Balance: ₹{money(updated_balance):,.2f}",
    })


@banking_bp.delete("/connections/<int:connection_id>")
@api_login_required
def api_disconnect_bank(connection_id: int):
    """Disconnect a bank account."""
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM bank_connections WHERE id = ? AND user_id = ?",
            (connection_id, _current_user()["id"]),
        )
        conn.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Beneficiaries
# ---------------------------------------------------------------------------


@banking_bp.get("/beneficiaries")
@api_login_required
def api_beneficiaries():
    """List saved beneficiaries."""
    with closing(get_db()) as conn:
        beneficiaries = conn.execute(
            "SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY favorite DESC, name",
            (_current_user()["id"],),
        ).fetchall()
    return jsonify({"beneficiaries": [dict(b) for b in beneficiaries]})


@banking_bp.post("/beneficiaries")
@api_login_required
def api_add_beneficiary():
    """Add a beneficiary."""
    user_id = _current_user()["id"]
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    account_number = (body.get("account_number") or "").strip()
    ifsc = (body.get("ifsc") or "").strip()
    upi_id = (body.get("upi_id") or "").strip()
    bank_name = (body.get("bank_name") or "").strip()

    if not name or (not account_number and not upi_id):
        return jsonify({"error": "Name and either account number or UPI ID required."}), 400

    with closing(get_db()) as conn:
        # Verify account if details provided
        verified = 0
        if account_number and ifsc:
            from finance.banking import verify_bank_account
            is_valid, holder_name = verify_bank_account(account_number, ifsc)
            verified = 1 if is_valid else 0

        cursor = conn.execute(
            """
            INSERT INTO beneficiaries (user_id, name, account_number, ifsc, upi_id, bank_name, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, account_number, ifsc, upi_id, bank_name, verified),
        )
        conn.commit()
        beneficiary = conn.execute(
            "SELECT * FROM beneficiaries WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    return jsonify({"beneficiary": dict(beneficiary)}), 201


@banking_bp.delete("/beneficiaries/<int:beneficiary_id>")
@api_login_required
def api_delete_beneficiary(beneficiary_id: int):
    """Delete a beneficiary."""
    with closing(get_db()) as conn:
        conn.execute(
            "DELETE FROM beneficiaries WHERE id = ? AND user_id = ?",
            (beneficiary_id, _current_user()["id"]),
        )
        conn.commit()
    return jsonify({"ok": True})


@banking_bp.post("/beneficiaries/<int:beneficiary_id>/favorite")
@api_login_required
def api_toggle_favorite(beneficiary_id: int):
    """Toggle favorite status."""
    with closing(get_db()) as conn:
        beneficiary = conn.execute(
            "SELECT * FROM beneficiaries WHERE id = ? AND user_id = ?",
            (beneficiary_id, _current_user()["id"]),
        ).fetchone()
        if not beneficiary:
            return jsonify({"error": "Beneficiary not found."}), 404
        new_fav = 0 if beneficiary["favorite"] else 1
        conn.execute(
            "UPDATE beneficiaries SET favorite = ? WHERE id = ?",
            (new_fav, beneficiary_id),
        )
        conn.commit()
    return jsonify({"favorite": bool(new_fav)})


# ---------------------------------------------------------------------------
# Bank transfers (NEFT/IMPS)
# ---------------------------------------------------------------------------


@banking_bp.post("/transfer")
@api_login_required
def api_transfer():
    """Send money via bank transfer."""
    user = _current_user()
    body = request.get_json(silent=True) or {}
    from_account_id = body.get("from_account_id", type=int)
    beneficiary_id = body.get("beneficiary_id", type=int)
    amount = body.get("amount", type=float)
    reference = (body.get("reference") or "").strip()

    if not from_account_id or not amount:
        return jsonify({"error": "From account and amount are required."}), 400

    # Get beneficiary details
    with closing(get_db()) as conn:
        if beneficiary_id:
            ben = conn.execute(
                "SELECT * FROM beneficiaries WHERE id = ? AND user_id = ?",
                (beneficiary_id, user["id"]),
            ).fetchone()
            if not ben:
                return jsonify({"error": "Beneficiary not found."}), 404
            beneficiary_name = ben["name"]
            beneficiary_account = ben["account_number"]
            beneficiary_ifsc = ben["ifsc"]
            beneficiary_upi = ben["upi_id"]
        else:
            beneficiary_name = (body.get("beneficiary_name") or "").strip()
            beneficiary_account = (body.get("beneficiary_account") or "").strip()
            beneficiary_ifsc = (body.get("beneficiary_ifsc") or "").strip()
            beneficiary_upi = None

            if not beneficiary_name or not beneficiary_account or not beneficiary_ifsc:
                return jsonify({"error": "Beneficiary details incomplete."}), 400

    # Process the transfer
    success, message, data = process_bank_transfer(
        user["id"], from_account_id, beneficiary_name,
        beneficiary_account, beneficiary_ifsc, amount, reference,
    )

    if not success:
        return jsonify({"error": message}), 400

    # Record the transfer
    with closing(get_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO payment_transfers (user_id, from_account_id, beneficiary_name,
                beneficiary_account, beneficiary_ifsc, beneficiary_upi, amount,
                status, utr, reference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], from_account_id, beneficiary_name, beneficiary_account,
             beneficiary_ifsc, beneficiary_upi, money(amount),
             PaymentStatus.SUCCESS.value, data["utr"], data["reference"]),
        )
        transfer_id = cursor.lastrowid

        # Deduct from account
        conn.execute(
            "UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?",
            (money(amount), from_account_id, user["id"]),
        )

        # Record as transaction
        conn.execute(
            """
            INSERT INTO transactions (user_id, account_id, description, amount, category, type, transaction_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], from_account_id, f"Transfer to {beneficiary_name}",
             money(amount), "Bank Transfer", "expense", date.today().isoformat(),
             f"UTR: {data['utr']} | Ref: {data['reference']} | To: {beneficiary_account}"),
        )
        conn.commit()

    return jsonify({
        "transfer_id": transfer_id,
        "utr": data["utr"],
        "status": "success",
        "message": message,
    }), 201


@banking_bp.get("/transfers")
@api_login_required
def api_transfers():
    """List transfers made by the user."""
    with closing(get_db()) as conn:
        transfers = conn.execute(
            """
            SELECT pt.*, a.name AS from_account_name
            FROM payment_transfers pt
            LEFT JOIN accounts a ON a.id = pt.from_account_id
            WHERE pt.user_id = ?
            ORDER BY pt.initiated_at DESC
            LIMIT 50
            """,
            (_current_user()["id"],),
        ).fetchall()
    return jsonify({"transfers": [dict(t) for t in transfers]})


# ---------------------------------------------------------------------------
# UPI Payments
# ---------------------------------------------------------------------------


@banking_bp.post("/upi/pay")
@api_login_required
def api_upi_pay():
    """Pay via UPI."""
    user = _current_user()
    body = request.get_json(silent=True) or {}
    to_upi_id = (body.get("to_upi_id") or "").strip()
    amount = body.get("amount", type=float)
    note = (body.get("note") or "").strip()

    if not to_upi_id or not amount:
        return jsonify({"error": "UPI ID and amount are required."}), 400

    # Get user's primary UPI ID
    with closing(get_db()) as conn:
        upi = conn.execute(
            "SELECT upi_id FROM user_upi_ids WHERE user_id = ? AND is_primary = 1",
            (user["id"],),
        ).fetchone()
        if not upi:
            return jsonify({"error": "No UPI ID found. Link a bank account first."}), 400

        from_upi_id = upi["upi_id"]

    # Process UPI payment
    success, message, data = process_upi_payment(
        user["id"], from_upi_id, to_upi_id, amount, note,
    )

    if not success:
        return jsonify({"error": message}), 400

    # Record
    with closing(get_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO upi_payments (user_id, from_upi_id, to_upi_id, amount, note, status, txn_id, utr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], from_upi_id, to_upi_id, money(amount), note,
             PaymentStatus.SUCCESS.value, data["txn_id"], data["utr"]),
        )
        conn.commit()

    return jsonify({
        "payment_id": cursor.lastrowid,
        "txn_id": data["txn_id"],
        "utr": data["utr"],
        "from_upi": from_upi_id,
        "to_upi": to_upi_id,
        "amount": money(amount),
        "status": "success",
        "message": message,
    }), 201


@banking_bp.get("/upi/payments")
@api_login_required
def api_upi_payments():
    """List UPI payments."""
    with closing(get_db()) as conn:
        payments = conn.execute(
            "SELECT * FROM upi_payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (_current_user()["id"],),
        ).fetchall()
    return jsonify({"payments": [dict(p) for p in payments]})


@banking_bp.get("/upi/qr")
@api_login_required
def api_generate_qr():
    """Generate UPI QR code string for receiving payment."""
    user = _current_user()
    amount = request.args.get("amount", type=float)
    note = request.args.get("note", "Payment")

    with closing(get_db()) as conn:
        upi = conn.execute(
            "SELECT upi_id FROM user_upi_ids WHERE user_id = ? AND is_primary = 1",
            (user["id"],),
        ).fetchone()
        if not upi:
            return jsonify({"error": "No UPI ID found."}), 400

    qr_string = generate_qr_upi_string(upi["upi_id"], amount or 0.0, note)
    return jsonify({
        "upi_id": upi["upi_id"],
        "qr_string": qr_string,
        "amount": money(amount) if amount else 0,
        "note": note,
    })


# ---------------------------------------------------------------------------
# Bill Payments
# ---------------------------------------------------------------------------


@banking_bp.get("/billers")
def api_billers():
    """List available billers by category."""
    category = request.args.get("category", "").strip()
    if category and category in BILLERS:
        return jsonify({"billers": BILLERS[category], "category": category})
    return jsonify({"categories": {k: v for k, v in BILLERS.items()}})


@banking_bp.post("/bills/fetch")
@api_login_required
def api_fetch_bill():
    """Fetch bill amount from a biller."""
    body = request.get_json(silent=True) or {}
    biller_code = (body.get("biller_code") or "").strip()
    consumer_number = (body.get("consumer_number") or "").strip()

    if not biller_code or not consumer_number:
        return jsonify({"error": "Biller code and consumer number required."}), 400

    bill = get_bill_amount(biller_code, consumer_number)
    if not bill:
        return jsonify({"error": "Could not fetch bill. Check the consumer number."}), 404

    return jsonify({"bill": bill})


@banking_bp.post("/bills/pay")
@api_login_required
def api_pay_bill():
    """Pay a bill."""
    user = _current_user()
    body = request.get_json(silent=True) or {}
    biller_code = (body.get("biller_code") or "").strip()
    biller_name = (body.get("biller_name") or "").strip()
    consumer_number = (body.get("consumer_number") or "").strip()
    amount = body.get("amount", type=float)
    from_account_id = body.get("from_account_id", type=int)

    if not biller_code or not consumer_number or not amount or not from_account_id:
        return jsonify({"error": "All fields are required."}), 400

    # Process payment
    success, message, data = process_bill_payment(
        biller_code, consumer_number, amount, user["id"], from_account_id,
    )

    if not success:
        return jsonify({"error": message}), 400

    # Record
    with closing(get_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO bill_payments (user_id, from_account_id, biller_code, biller_name,
                consumer_number, amount, status, reference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user["id"], from_account_id, biller_code, biller_name or biller_code,
             consumer_number, money(amount), "success", data["reference"]),
        )
        conn.commit()

    return jsonify({
        "payment_id": cursor.lastrowid,
        "reference": data["reference"],
        "status": "success",
        "message": message,
    }), 201


@banking_bp.get("/bills/history")
@api_login_required
def api_bill_history():
    """List bill payments."""
    with closing(get_db()) as conn:
        bills = conn.execute(
            """
            SELECT bp.*, a.name AS account_name
            FROM bill_payments bp
            LEFT JOIN accounts a ON a.id = bp.from_account_id
            WHERE bp.user_id = ?
            ORDER BY bp.paid_at DESC LIMIT 50
            """,
            (_current_user()["id"],),
        ).fetchall()
    return jsonify({"bills": [dict(b) for b in bills]})


@banking_bp.post("/bills/reminders")
@api_login_required
def api_add_bill_reminder():
    """Add a bill reminder for auto-pay or notifications."""
    user_id = _current_user()["id"]
    body = request.get_json(silent=True) or {}
    biller_code = (body.get("biller_code") or "").strip()
    consumer_number = (body.get("consumer_number") or "").strip()
    nickname = (body.get("nickname") or "").strip()
    auto_pay = 1 if body.get("auto_pay") else 0
    remind_before_days = body.get("remind_before_days", 3)

    with closing(get_db()) as conn:
        existing = conn.execute(
            "SELECT id FROM bill_reminders WHERE user_id = ? AND biller_code = ? AND consumer_number = ?",
            (user_id, biller_code, consumer_number),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE bill_reminders SET auto_pay = ?, remind_before_days = ?, nickname = ? WHERE id = ?",
                (auto_pay, remind_before_days, nickname, existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO bill_reminders (user_id, biller_code, consumer_number, nickname, auto_pay, remind_before_days)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, biller_code, consumer_number, nickname, auto_pay, remind_before_days),
            )
        conn.commit()

    return jsonify({"ok": True})


@banking_bp.get("/bills/reminders")
@api_login_required
def api_bill_reminders():
    """List bill reminders."""
    with closing(get_db()) as conn:
        reminders = conn.execute(
            "SELECT * FROM bill_reminders WHERE user_id = ? AND active = 1 ORDER BY biller_code",
            (_current_user()["id"],),
        ).fetchall()
    return jsonify({"reminders": [dict(r) for r in reminders]})


# ---------------------------------------------------------------------------
# Banking dashboard summary
# ---------------------------------------------------------------------------


@banking_bp.get("/summary")
@api_login_required
def api_banking_summary():
    """Get full banking summary for the user."""
    user_id = _current_user()["id"]
    with closing(get_db()) as conn:
        connections = conn.execute(
            "SELECT * FROM bank_connections WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchall()
        upi_ids = conn.execute(
            "SELECT * FROM user_upi_ids WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        recent_transfers = conn.execute(
            "SELECT * FROM payment_transfers WHERE user_id = ? ORDER BY initiated_at DESC LIMIT 5",
            (user_id,),
        ).fetchall()
        recent_bills = conn.execute(
            "SELECT * FROM bill_payments WHERE user_id = ? ORDER BY paid_at DESC LIMIT 5",
            (user_id,),
        ).fetchall()
        beneficiaries = conn.execute(
            "SELECT * FROM beneficiaries WHERE user_id = ? ORDER BY favorite DESC, name LIMIT 10",
            (user_id,),
        ).fetchall()

    return jsonify({
        "connected_banks": len(connections),
        "connections": [dict(c) for c in connections],
        "upi_ids": [dict(u) for u in upi_ids],
        "recent_transfers": [dict(t) for t in recent_transfers],
        "recent_bills": [dict(b) for b in recent_bills],
        "beneficiaries": [dict(b) for b in beneficiaries],
    })