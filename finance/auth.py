from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from finance.config import JWT_EXPIRY_HOURS, JWT_SECRET
from finance.db import get_db, user_to_dict


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def authenticate_user(email: str, password: str) -> dict | None:
    with closing(get_db()) as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if user and verify_password(user["password_hash"], password):
        return user_to_dict(user)
    return None


def register_user(name: str, email: str, password: str, currency: str = "USD") -> dict:
    with closing(get_db()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash, currency)
            VALUES (?, ?, ?, ?)
            """,
            (name, email.lower(), hash_password(password), currency),
        )
        conn.commit()
        user_id = cursor.lastrowid
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return user_to_dict(user)


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
        if not token:
            return jsonify({"error": "Authentication required."}), 401
        user_id = decode_access_token(token)
        if user_id is None:
            return jsonify({"error": "Invalid or expired token."}), 401
        with closing(get_db()) as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return jsonify({"error": "User not found."}), 401
        g.api_user = user
        return view(*args, **kwargs)

    return wrapped
