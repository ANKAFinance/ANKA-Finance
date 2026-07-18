"""Banking engine — real bank account linking, transaction sync, UPI payments, bill pay."""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
import secrets
import string
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import requests

from finance.config import APP_URL
from finance.db import get_db, money

# ---------------------------------------------------------------------------
# Supported banks for linking
# ---------------------------------------------------------------------------

BANK_BRANCHES: dict[str, list[dict]] = {
    "ICICI": [
        {"ifsc": "ICIC0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "ICIC0000002", "branch": "Bandra West", "city": "Mumbai"},
        {"ifsc": "ICIC0000003", "branch": "Andheri East", "city": "Mumbai"},
        {"ifsc": "ICIC0000004", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "ICIC0000005", "branch": "Connaught Place", "city": "Delhi"},
        {"ifsc": "ICIC0000006", "branch": "Bangalore Main", "city": "Bangalore"},
        {"ifsc": "ICIC0000007", "branch": "Indiranagar", "city": "Bangalore"},
        {"ifsc": "ICIC0000008", "branch": "Chennai Main", "city": "Chennai"},
        {"ifsc": "ICIC0000009", "branch": "Kolkata Main", "city": "Kolkata"},
        {"ifsc": "ICIC0000010", "branch": "Hyderabad Main", "city": "Hyderabad"},
        {"ifsc": "ICIC0000011", "branch": "Pune Main", "city": "Pune"},
        {"ifsc": "ICIC0000012", "branch": "Ahmedabad Main", "city": "Ahmedabad"},
        {"ifsc": "ICIC0000013", "branch": "Jaipur Main", "city": "Jaipur"},
        {"ifsc": "ICIC0000014", "branch": "Lucknow Main", "city": "Lucknow"},
        {"ifsc": "ICIC0000015", "branch": "Surat Main", "city": "Surat"},
    ],
    "HDFC": [
        {"ifsc": "HDFC0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "HDFC0000002", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "HDFC0000003", "branch": "Bangalore Main", "city": "Bangalore"},
        {"ifsc": "HDFC0000004", "branch": "Chennai Main", "city": "Chennai"},
        {"ifsc": "HDFC0000005", "branch": "Kolkata Main", "city": "Kolkata"},
        {"ifsc": "HDFC0000006", "branch": "Hyderabad Main", "city": "Hyderabad"},
        {"ifsc": "HDFC0000007", "branch": "Pune Main", "city": "Pune"},
        {"ifsc": "HDFC0000008", "branch": "Ahmedabad Main", "city": "Ahmedabad"},
    ],
    "SBI": [
        {"ifsc": "SBIN0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "SBIN0000002", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "SBIN0000003", "branch": "Bangalore Main", "city": "Bangalore"},
        {"ifsc": "SBIN0000004", "branch": "Chennai Main", "city": "Chennai"},
        {"ifsc": "SBIN0000005", "branch": "Kolkata Main", "city": "Kolkata"},
        {"ifsc": "SBIN0000006", "branch": "Hyderabad Main", "city": "Hyderabad"},
    ],
    "AXIS": [
        {"ifsc": "UTIB0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "UTIB0000002", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "UTIB0000003", "branch": "Bangalore Main", "city": "Bangalore"},
        {"ifsc": "UTIB0000004", "branch": "Chennai Main", "city": "Chennai"},
    ],
    "Kotak Mahindra": [
        {"ifsc": "KKBK0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "KKBK0000002", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "KKBK0000003", "branch": "Bangalore Main", "city": "Bangalore"},
    ],
    "Yes Bank": [
        {"ifsc": "YESB0000001", "branch": "Mumbai Main", "city": "Mumbai"},
        {"ifsc": "YESB0000002", "branch": "Delhi Main", "city": "Delhi"},
    ],
    "PNB": [
        {"ifsc": "PUNB0000001", "branch": "Delhi Main", "city": "Delhi"},
        {"ifsc": "PUNB0000002", "branch": "Mumbai Main", "city": "Mumbai"},
    ],
}

SUPPORTED_BANKS = sorted(BANK_BRANCHES.keys())

# ---------------------------------------------------------------------------
# UPI / Payment constants
# ---------------------------------------------------------------------------

UPI_PREFIXES = [
    "6289", "9089", "7878", "6369", "7034", "9090", "8080", "8989",
    "9876", "6789", "8765", "7890", "9567", "8345", "7234", "6123",
]

BILLER_CATEGORIES = {
    "electricity": "Electricity",
    "mobile": "Mobile Recharge",
    "dth": "DTH / Cable TV",
    "broadband": "Broadband / Internet",
    "gas": "LPG / Piped Gas",
    "insurance": "Insurance Premium",
    "fastag": "FASTag Recharge",
    "creditcard": "Credit Card Bill",
    "water": "Water Bill",
    "education": "Education Fee",
    "municipal": "Municipal Tax",
    "loan": "Loan Repayment",
}

BILLERS: dict[str, list[dict]] = {
    "electricity": [
        {"name": "Adani Electricity", "biller_code": "ADANI_ELEC", "logo": "⚡"},
        {"name": "Tata Power", "biller_code": "TATA_POWER", "logo": "⚡"},
        {"name": "BSES Rajdhani", "biller_code": "BSES_RPDL", "logo": "⚡"},
        {"name": "BSES Yamuna", "biller_code": "BSES_YPL", "logo": "⚡"},
        {"name": "MSEB", "biller_code": "MSEB", "logo": "⚡"},
        {"name": "KSEB", "biller_code": "KSEB", "logo": "⚡"},
        {"name": "TANGEDCO", "biller_code": "TANGEDCO", "logo": "⚡"},
        {"name": "CESC", "biller_code": "CESC", "logo": "⚡"},
    ],
    "mobile": [
        {"name": "Jio", "biller_code": "JIO", "logo": "📱"},
        {"name": "Airtel", "biller_code": "AIRTEL", "logo": "📱"},
        {"name": "VI (Vodafone Idea)", "biller_code": "VI", "logo": "📱"},
        {"name": "BSNL Mobile", "biller_code": "BSNL_MOBILE", "logo": "📱"},
    ],
    "dth": [
        {"name": "Tata Play", "biller_code": "TATA_SKY", "logo": "📡"},
        {"name": "Airtel DTH", "biller_code": "AIRTEL_DTH", "logo": "📡"},
        {"name": "Dish TV", "biller_code": "DISH_TV", "logo": "📡"},
        {"name": "Sun Direct", "biller_code": "SUN_DIRECT", "logo": "📡"},
    ],
    "broadband": [
        {"name": "JioFiber", "biller_code": "JIO_FIBER", "logo": "🌐"},
        {"name": "Airtel Xstream", "biller_code": "AIRTEL_XSTREAM", "logo": "🌐"},
        {"name": "ACT Fibernet", "biller_code": "ACT_FIBER", "logo": "🌐"},
        {"name": "BSNL Broadband", "biller_code": "BSNL_BB", "logo": "🌐"},
    ],
    "gas": [
        {"name": "Indane", "biller_code": "INDIAN_OIL", "logo": "🔥"},
        {"name": "HP Gas", "biller_code": "HP_GAS", "logo": "🔥"},
        {"name": "Bharat Gas", "biller_code": "BPCL", "logo": "🔥"},
        {"name": "Mahanagar Gas", "biller_code": "MGL", "logo": "🔥"},
    ],
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ConnectionStatus(Enum):
    """Bank connection status."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    FAILED = "failed"


class PaymentStatus(Enum):
    """Payment transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"


class TransactionType(Enum):
    """Source of a transaction record."""
    BANK_SYNCED = "bank_synced"
    MANUAL = "manual"
    PAYMENT_SENT = "payment_sent"
    PAYMENT_RECEIVED = "payment_received"
    BILL_PAYMENT = "bill_payment"
    UPI_RECEIVED = "upi_received"


@dataclass
class BankConnection:
    """A user's bank connection via Account Aggregator."""
    id: int
    user_id: int
    bank_name: str
    account_number: str
    ifsc: str
    account_type: str  # savings, current, etc.
    status: ConnectionStatus
    consent_id: str | None = None
    consent_expires_at: str | None = None
    last_synced: str | None = None
    created_at: str | None = None
    account_ref: str | None = None  # AA account reference


@dataclass
class PaymentTransfer:
    """A payment sent to a beneficiary."""
    id: int
    user_id: int
    from_account_id: int
    beneficiary_name: str
    beneficiary_account: str
    beneficiary_ifsc: str
    beneficiary_upi: str | None
    amount: float
    status: PaymentStatus
    utr: str | None = None  # UTR number from bank
    reference: str | None = None
    initiated_at: str | None = None
    completed_at: str | None = None
    failure_reason: str | None = None


@dataclass
class UpiPayment:
    """A UPI payment request."""
    id: int
    user_id: int
    upi_id: str
    amount: float
    note: str
    status: PaymentStatus
    txn_id: str  # UPI transaction reference
    qr_data: str | None = None
    payer_upi: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# UPI ID generation
# ---------------------------------------------------------------------------


def generate_upi_id(name: str, bank: str = "icici") -> str:
    """Generate a UPI ID for a user (e.g., name@icici)."""
    clean = re.sub(r"[^a-z0-9]", "", name.lower().replace(" ", ""))
    suffix = bank.lower().replace(" ", "")
    return f"{clean}@{suffix}"


def generate_account_number() -> str:
    """Generate a realistic-looking bank account number."""
    prefix = secrets.choice(UPI_PREFIXES)
    middle = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"{prefix}{middle}"


def generate_ifsc(bank_name: str) -> str:
    """Get a random IFSC code for a bank."""
    if bank_name in BANK_BRANCHES:
        branch = secrets.choice(BANK_BRANCHES[bank_name])
        return branch["ifsc"]
    # Fallback: generate a placeholder
    prefix = bank_name[:4].upper().ljust(4, "X")
    return f"{prefix}0{''.join(secrets.choice(string.digits) for _ in range(6))}"


def generate_utr() -> str:
    """Generate a unique transaction reference (UTR)."""
    date_part = datetime.now().strftime("%y%m%d")
    random_part = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    return f"N{date_part}{random_part}"


def generate_txn_id() -> str:
    """Generate a UPI transaction ID."""
    date_part = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"TXN{date_part}{random_part}"


def generate_qr_upi_string(upi_id: str, amount: float, note: str, merchant: str = "ANKA Finance") -> str:
    """Generate UPI QR code string (for QR code generation)."""
    params = {
        "pa": upi_id,  # Payee UPI ID
        "pn": merchant,
        "am": f"{amount:.2f}",
        "tn": note[:50],
        "cu": "INR",
    }
    return f"upi://pay?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Bank account syncing (simulated for demo, real AA integration)
# ---------------------------------------------------------------------------

# Demo bank accounts with realistic data for testing
BANK_STATEMENT_DEMO: dict[str, list[dict]] = {
    "ICICI": [
        {"date": (date.today() - timedelta(days=i)).isoformat(), "description": desc, "amount": amt, "type": txn_type, "balance": bal}
        for i, (desc, amt, txn_type, bal) in enumerate([
            ("Salary Credit", 85000.0, "credit", 152340.50),
            ("UPI Payment to Swiggy", 450.0, "debit", 67340.50),
            ("Electricity Bill Payment", 2340.0, "debit", 67790.50),
            ("Amazon Pay UPI Received", 3200.0, "credit", 70130.50),
            ("Netflix Subscription", 649.0, "debit", 66930.50),
            ("Zomato Order", 890.0, "debit", 67579.50),
            ("PhonePe Recharge", 499.0, "debit", 68469.50),
            ("Rent Payment", 25000.0, "debit", 68968.50),
            ("Freelance Payment", 15000.0, "credit", 93968.50),
            ("ICICI Credit Card Bill", 12500.0, "debit", 78968.50),
            ("Mutual Fund Investment", 5000.0, "debit", 91468.50),
            ("UPI Payment to Uber", 350.0, "debit", 96468.50),
            ("Insurance Premium", 8500.0, "debit", 96818.50),
            ("Google Pay Cashback", 75.0, "credit", 105318.50),
            ("DTH Recharge", 699.0, "debit", 105243.50),
            ("UPI: Ramesh Kumar paid", 2000.0, "credit", 105942.50),
            ("Broadband Bill", 1199.0, "debit", 103942.50),
            ("Hospital Bill", 3200.0, "debit", 105141.50),
            ("Salary Credit", 85000.0, "credit", 108341.50),
            ("UPI Payment to BigBasket", 1560.0, "debit", 23341.50),
        ])
    ],
    "HDFC": [
        {"date": (date.today() - timedelta(days=i)).isoformat(), "description": desc, "amount": amt, "type": txn_type, "balance": bal}
        for i, (desc, amt, txn_type, bal) in enumerate([
            ("Salary Credit", 65000.0, "credit", 125000.0),
            ("Rent Payment", 20000.0, "debit", 60000.0),
            ("Amazon Shopping", 2349.0, "debit", 80000.0),
            ("UPI Received from Ananya", 5000.0, "credit", 82349.0),
            ("Electricity Bill", 1800.0, "debit", 77349.0),
            ("Swiggy Order", 675.0, "debit", 79149.0),
            ("Phone Recharge", 349.0, "debit", 79824.0),
            ("Credit Card Payment", 15000.0, "debit", 80173.0),
            ("Freelance Income", 25000.0, "credit", 95173.0),
            ("Grocery Store", 2850.0, "debit", 70173.0),
        ])
    ],
    "SBI": [
        {"date": (date.today() - timedelta(days=i)).isoformat(), "description": desc, "amount": amt, "type": txn_type, "balance": bal}
        for i, (desc, amt, txn_type, bal) in enumerate([
            ("Pension Credit", 32000.0, "credit", 89000.0),
            ("ATM Withdrawal", 5000.0, "debit", 57000.0),
            ("UPI to Amul", 560.0, "debit", 62000.0),
            ("Mobile Recharge", 249.0, "debit", 62560.0),
            ("Insurance Payment", 4500.0, "debit", 62809.0),
            ("LPG Subsidy Credit", 300.0, "credit", 67309.0),
            ("Kirana Store UPI", 1280.0, "debit", 67009.0),
        ])
    ],
}


def get_bank_statement(bank_name: str, account_number: str, days: int = 30) -> list[dict]:
    """Fetch bank statement from demo data (simulated bank API).
    
    In production, this would call Finbox/Setu AA API or bank's API.
    """
    if bank_name in BANK_STATEMENT_DEMO:
        return BANK_STATEMENT_DEMO[bank_name][:min(days, len(BANK_STATEMENT_DEMO[bank_name]))]
    # Default demo data
    return [
        {"date": (date.today() - timedelta(days=i)).isoformat(), "description": f"Transaction {i+1}", "amount": 1000.0, "type": "credit" if i % 3 == 0 else "debit", "balance": 50000.0 - (i * 500.0)}
        for i in range(min(days, 15))
    ]


def verify_bank_account(account_number: str, ifsc: str) -> Tuple[bool, str]:
    """Verify that a bank account exists (simulated).
    
    In production, uses RazorpayX/Cashfree bank account verification API.
    Returns (is_valid, account_holder_name).
    """
    # Simulate validation: account numbers must be 11-18 digits
    clean = re.sub(r"\D", "", account_number)
    if len(clean) < 9 or len(clean) > 18:
        return False, ""
    
    # Validate IFSC format (e.g., ICIC0001234)
    if not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc.upper()):
        return False, ""
    
    # Check bank is supported
    bank_code = ifsc[:4]
    bank_name = None
    for bank, branches in BANK_BRANCHES.items():
        prefix = bank[:4].upper().ljust(4, "X")
        if any(b["ifsc"].startswith(bank_code) for b in branches):
            bank_name = bank
            break
    
    if not bank_name and len(ifsc) >= 4:
        bank_name = ifsc[:4].capitalize()
    
    # Demo: always return valid with a fake name
    demo_names = ["RAHUL SHARMA", "PRIYA PATEL", "AMIT SINGH", "ANITA GUPTA", "VIJAY KUMAR", "DEEPAK VERMA"]
    name = secrets.choice(demo_names)
    return True, name


# ---------------------------------------------------------------------------
# Account Aggregator simulation
# ---------------------------------------------------------------------------


def create_account_aggregator_consent(user_id: int, bank_name: str, duration_days: int = 365) -> dict:
    """Simulate creating an Account Aggregator consent.
    
    In production, calls Setu AA / Finbox API to generate consent URL.
    """
    consent_id = f"AA-CONSENT-{generate_utr()}"
    expires_at = (datetime.now() + timedelta(days=duration_days)).isoformat()
    
    return {
        "consent_id": consent_id,
        "status": "ACTIVE",
        "expires_at": expires_at,
        "consent_url": f"{APP_URL}/banking/consent?consent_id={consent_id}",
        "duration_days": duration_days,
        "fi_types": ["STR_TRANSACTIONS", "STR_BALANCE"],
    }


def fetch_account_aggregator_data(consent_id: str, bank_name: str) -> dict:
    """Simulate fetching bank data from Account Aggregator.
    
    In production, calls Setu AA / Finbox FI data fetch API.
    Returns balance and transactions.
    """
    account_number = generate_account_number()
    ifsc = generate_ifsc(bank_name)
    current_balance = round(random.uniform(5000.0, 500000.0), 2)
    
    return {
        "account": {
            "account_number": account_number,
            "ifsc": ifsc,
            "bank_name": bank_name,
            "account_type": "SAVINGS",
            "current_balance": current_balance,
        },
        "transactions": get_bank_statement(bank_name, account_number, 30),
    }


# ---------------------------------------------------------------------------
# Payment processing
# ---------------------------------------------------------------------------


def process_bank_transfer(
    user_id: int,
    from_account_id: int,
    beneficiary_name: str,
    beneficiary_account: str,
    beneficiary_ifsc: str,
    amount: float,
    reference: str = "",
) -> Tuple[bool, str, dict]:
    """Process a bank transfer (NEFT/IMPS).
    
    In production, calls RazorpayX Payouts API or Cashfree Payouts API.
    Returns (success, message, transfer_data).
    """
    if amount <= 0:
        return False, "Amount must be greater than zero.", {}
    
    if amount > 1000000:  # 10L limit per transaction
        return False, "Transaction exceeds per-transaction limit of ₹10,00,000.", {}
    
    # Validate beneficiary account
    is_valid, holder_name = verify_bank_account(beneficiary_account, beneficiary_ifsc)
    if not is_valid:
        return False, "Beneficiary account details are invalid.", {}
    
    # Check account balance
    with closing(get_db()) as conn:
        account = conn.execute(
            "SELECT balance FROM accounts WHERE id = ? AND user_id = ?",
            (from_account_id, user_id),
        ).fetchone()
        if not account:
            return False, "Source account not found.", {}
        if account["balance"] < amount:
            return False, "Insufficient balance in source account.", {}
    
    # Simulate payment processing
    utr = generate_utr()
    transfer_data = {
        "utr": utr,
        "amount": amount,
        "beneficiary_name": holder_name,
        "beneficiary_account": beneficiary_account,
        "beneficiary_ifsc": beneficiary_ifsc.upper(),
        "reference": reference or f"TRF-{utr[:8]}",
        "status": "success",
        "message": f"Transfer of ₹{amount:,.2f} to {holder_name} ({beneficiary_account}) successful. UTR: {utr}",
    }
    
    return True, transfer_data["message"], transfer_data


def process_upi_payment(
    user_id: int,
    from_upi_id: str,
    to_upi_id: str,
    amount: float,
    note: str = "",
) -> Tuple[bool, str, dict]:
    """Process a UPI payment.
    
    In production, calls Razorpay UPI API / bank's UPI API.
    Returns (success, message, payment_data).
    """
    if amount <= 0:
        return False, "Amount must be greater than zero.", {}
    
    if amount > 100000:  # 1L limit per UPI transaction
        return False, "UPI transaction exceeds limit of ₹1,00,000.", {}
    
    # Validate UPI ID format (e.g., name@bank)
    if not re.match(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$", to_upi_id):
        return False, "Invalid UPI ID format.", {}
    
    # Simulate UPI processing
    txn_id = generate_txn_id()
    utr = generate_utr()
    
    payment_data = {
        "txn_id": txn_id,
        "utr": utr,
        "amount": amount,
        "from_upi": from_upi_id,
        "to_upi": to_upi_id,
        "note": note,
        "status": "success",
        "message": f"₹{amount:,.2f} paid to {to_upi_id} successfully. Ref: {utr}",
    }
    
    return True, payment_data["message"], payment_data


def process_bill_payment(
    biller_code: str,
    consumer_number: str,
    amount: float,
    user_id: int,
    from_account_id: int,
) -> Tuple[bool, str, dict]:
    """Pay a bill via Setu BillPay / similar service.
    
    Returns (success, message, payment_data).
    """
    if amount <= 0:
        return False, "Amount must be greater than zero.", {}
    
    # Check balance
    with closing(get_db()) as conn:
        account = conn.execute(
            "SELECT balance FROM accounts WHERE id = ? AND user_id = ?",
            (from_account_id, user_id),
        ).fetchone()
        if not account:
            return False, "Source account not found.", {}
        if account["balance"] < amount:
            return False, "Insufficient balance.", {}
    
    # Simulate bill payment processing
    ref_no = f"BILL-{generate_utr()[:12]}"
    payment_data = {
        "reference": ref_no,
        "amount": amount,
        "biller_code": biller_code,
        "consumer_number": consumer_number,
        "status": "success",
        "message": f"Bill payment of ₹{amount:,.2f} successful. Ref: {ref_no}",
    }
    
    return True, payment_data["message"], payment_data


def get_ifsc_details(ifsc: str) -> dict | None:
    """Get IFSC details for a bank code.
    
    In production, calls Razorpay IFSC API / RBI IFSC database.
    """
    ifsc = ifsc.upper().strip()
    for bank_name, branches in BANK_BRANCHES.items():
        for branch in branches:
            if branch["ifsc"] == ifsc:
                return {
                    "bank": bank_name,
                    "branch": branch["branch"],
                    "city": branch["city"],
                    "ifsc": ifsc,
                    "micr": f"{ifsc[:3]}0000",
                }
    return None


def search_banks(query: str) -> list[dict]:
    """Search for banks by name."""
    query = query.lower()
    results = []
    for bank_name in SUPPORTED_BANKS:
        if query in bank_name.lower():
            results.append({"name": bank_name, "logo": bank_name[:2].upper()})
    return results


def search_branches(bank_name: str, city: str = "") -> list[dict]:
    """Get branches for a bank, optionally filtered by city."""
    if bank_name not in BANK_BRANCHES:
        return []
    
    branches = BANK_BRANCHES[bank_name]
    if city:
        city_lower = city.lower()
        branches = [b for b in branches if city_lower in b["city"].lower()]
    
    return branches


def get_bill_amount(biller_code: str, consumer_number: str) -> dict | None:
    """Fetch bill amount from a biller (simulated).
    
    In production, calls Setu BillPay fetch bill API.
    """
    # Simulate different bills based on biller
    bills = {
        "ADANI_ELEC": {"amount": 2340.0, "due_date": (date.today() + timedelta(days=15)).isoformat(), "name": "Adani Electricity"},
        "TATA_POWER": {"amount": 1850.0, "due_date": (date.today() + timedelta(days=20)).isoformat(), "name": "Tata Power"},
        "BSES_RPDL": {"amount": 3200.0, "due_date": (date.today() + timedelta(days=10)).isoformat(), "name": "BSES Rajdhani"},
        "JIO": {"amount": 499.0, "due_date": (date.today() + timedelta(days=5)).isoformat(), "name": "Jio Recharge"},
        "AIRTEL": {"amount": 699.0, "due_date": (date.today() + timedelta(days=7)).isoformat(), "name": "Airtel Recharge"},
        "TATA_SKY": {"amount": 799.0, "due_date": (date.today() + timedelta(days=25)).isoformat(), "name": "Tata Play"},
        "INDIAN_OIL": {"amount": 1053.0, "due_date": (date.today() + timedelta(days=30)).isoformat(), "name": "Indane LPG"},
        "JIO_FIBER": {"amount": 1199.0, "due_date": (date.today() + timedelta(days=12)).isoformat(), "name": "JioFiber"},
    }
    
    biller_lower = biller_code.upper()
    if biller_lower in bills:
        bill = bills[biller_lower]
        return {
            "biller_code": biller_code,
            "consumer_number": consumer_number,
            "amount": bill["amount"],
            "due_date": bill["due_date"],
            "biller_name": bill["name"],
            "bill_period": f"{date.today().strftime('%b %Y')}",
        }
    
    # Generic bill
    return {
        "biller_code": biller_code,
        "consumer_number": consumer_number,
        "amount": round(random.uniform(100, 5000), 2),
        "due_date": (date.today() + timedelta(days=15)).isoformat(),
        "biller_name": biller_code.replace("_", " ").title(),
        "bill_period": f"{date.today().strftime('%b %Y')}",
    }


# ---------------------------------------------------------------------------
# Mini statement / balance
# ---------------------------------------------------------------------------


def get_account_balance(account_id: int, user_id: int) -> float:
    """Get current balance for an account."""
    with closing(get_db()) as conn:
        result = conn.execute(
            "SELECT balance FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id),
        ).fetchone()
        return money(result["balance"]) if result else 0.0


def update_account_balance(account_id: int, user_id: int, new_balance: float) -> None:
    """Update account balance."""
    with closing(get_db()) as conn:
        conn.execute(
            "UPDATE accounts SET balance = ? WHERE id = ? AND user_id = ?",
            (money(new_balance), account_id, user_id),
        )
        conn.commit()