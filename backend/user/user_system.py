"""Simple in-memory auth/user system."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Header, HTTPException


USERS: dict[str, dict] = {}
TOKENS: dict[str, str] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(username: str, password: str, email: str | None = None) -> dict:
    if username in USERS:
        raise HTTPException(status_code=400, detail="username already exists")
    user_id = f"u_{uuid4().hex[:8]}"
    USERS[username] = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"user_id": user_id}


def login_user(username: str, password: str) -> dict:
    user = USERS.get(username)
    if not user or user["password_hash"] != _hash_password(password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = f"tok_{uuid4().hex}"
    TOKENS[token] = user["user_id"]
    return {
        "token": token,
        "expires_in": 7200,
        "user": {"user_id": user["user_id"], "username": username},
    }


def get_user_by_token(token: str) -> dict:
    user_id = TOKENS.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="token invalid")
    for user in USERS.values():
        if user["user_id"] == user_id:
            return {k: v for k, v in user.items() if k != "password_hash"}
    raise HTTPException(status_code=401, detail="token invalid")


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_by_token(token)

