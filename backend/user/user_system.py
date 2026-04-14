from __future__ import annotations
"""Simple in-memory auth/user system.

NOTE: This module uses in-memory dicts (USERS / TOKENS) so that the app
can run and be tested without a database connection.  When you are ready to
switch to a real database, replace the dict lookups with SQLAlchemy queries
against `backend.db.models.User` (and a new UserToken model).
"""

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Header, HTTPException


# ---------------------------------------------------------------------------
# In-memory stores – cleared between tests by conftest.py
# ---------------------------------------------------------------------------
USERS: dict[str, dict] = {}   # keyed by user_id
TOKENS: dict[str, dict] = {}  # keyed by token string


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(username: str, password: str, email: str | None = None) -> dict:
    """Register a new user (in-memory)."""
    for u in USERS.values():
        if u["username"] == username:
            raise HTTPException(status_code=400, detail="username already exists")

    user_id = f"u_{uuid4().hex[:8]}"
    USERS[user_id] = {
        "user_id": user_id,
        "username": username,
        "password": _hash_password(password),
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"user_id": user_id}


def login_user(username: str, password: str) -> dict:
    """Authenticate and return a bearer token."""
    matched = next((u for u in USERS.values() if u["username"] == username), None)
    if not matched:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if matched["password"] != _hash_password(password):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = f"tok_{uuid4().hex}"
    TOKENS[token] = {"user_id": matched["user_id"], "username": matched["username"]}
    return {
        "token": token,
        "expires_in": 7200,
        "user": {"user_id": matched["user_id"], "username": matched["username"]},
    }


def get_user_by_token(token: str) -> dict:
    """Resolve a token to a user dict."""
    record = TOKENS.get(token)
    if not record:
        raise HTTPException(status_code=401, detail="token invalid or expired")
    user = USERS.get(record["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return {"user_id": user["user_id"], "username": user["username"], "email": user.get("email")}


def get_current_user(authorization: str = Header(default="")) -> dict:
    """Extract and validate the Bearer token from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_by_token(token)


def logout_user(token: str) -> dict:
    """Invalidate a token (in-memory)."""
    if token not in TOKENS:
        raise HTTPException(status_code=400, detail="token not exists")
    del TOKENS[token]
    return {"message": "logged out"}