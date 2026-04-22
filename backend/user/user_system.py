from __future__ import annotations
"""Dual-mode auth/user system: in-memory (default) or database-backed.

Set ``USE_DB = True`` and call ``set_db_session_factory(factory)`` to switch
to database mode.  When ``USE_DB`` is ``False`` the module falls back to
plain Python dicts (``USERS`` / ``TOKENS``), which is ideal for unit tests
that don't need a real database.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Header, HTTPException


# ---------------------------------------------------------------------------
# Mode toggle – flipped by conftest.py or application bootstrap
# ---------------------------------------------------------------------------
USE_DB: bool = True
_session_factory = None  # set via set_db_session_factory()


def set_db_session_factory(factory) -> None:
    """Inject a SQLAlchemy sessionmaker so the module can talk to the DB."""
    global _session_factory
    _session_factory = factory


def _get_session():
    if _session_factory is None:
        raise RuntimeError("DB mode enabled but no session factory configured")
    return _session_factory()


# ---------------------------------------------------------------------------
# In-memory stores – used when USE_DB is False
# ---------------------------------------------------------------------------
USERS: dict[str, dict] = {}
TOKENS: dict[str, dict] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ===== register =====
def register_user(username: str, password: str, email: str | None = None) -> dict:
    if USE_DB:
        return _register_user_db(username, password, email)
    return _register_user_mem(username, password, email)


def _register_user_mem(username: str, password: str, email: str | None) -> dict:
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


def _register_user_db(username: str, password: str, email: str | None) -> dict:
    from backend.db.models import User
    session = _get_session()
    try:
        if session.query(User).filter_by(username=username).first():
            raise HTTPException(status_code=400, detail="username already exists")
        new_user = User(username=username, password=_hash_password(password), email=email)
        session.add(new_user)
        session.commit()
        return {"user_id": str(new_user.id)}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ===== login =====
def login_user(username: str, password: str) -> dict:
    if USE_DB:
        return _login_user_db(username, password)
    return _login_user_mem(username, password)


def _login_user_mem(username: str, password: str) -> dict:
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


def _login_user_db(username: str, password: str) -> dict:
    from backend.db.models import User, UserToken
    session = _get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user or user.password != _hash_password(password):
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = f"tok_{uuid4().hex}"
        expired_time = datetime.now() + timedelta(seconds=7200)
        session.add(UserToken(user_id=user.id, token=token, expired_time=expired_time))
        session.commit()
        return {
            "token": token,
            "expires_in": 7200,
            "user": {
                "user_id": str(user.id),
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "bio": user.bio,
                "music_taste": user.music_taste
            },
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ===== token lookup =====
def get_user_by_token(token: str) -> dict:
    if USE_DB:
        return _get_user_by_token_db(token)
    return _get_user_by_token_mem(token)


def _get_user_by_token_mem(token: str) -> dict:
    record = TOKENS.get(token)
    if not record:
        raise HTTPException(status_code=401, detail="token invalid or expired")
    user = USERS.get(record["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return {"user_id": user["user_id"], "username": user["username"], "email": user.get("email")}


def _get_user_by_token_db(token: str) -> dict:
    from backend.db.models import User, UserToken
    session = _get_session()
    try:
        now = datetime.now()
        tok = session.query(UserToken).filter(UserToken.token == token, UserToken.expired_time > now).first()
        if not tok:
            raise HTTPException(status_code=401, detail="token invalid or expired")
        user = session.get(User, tok.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="user not found")
        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "bio": user.bio,
            "birthday": user.birthday,
            "music_taste": user.music_taste,
        }
    finally:
        session.close()


def update_user_info(user_id: str, data: dict) -> dict:
    if USE_DB:
        return _update_user_info_db(user_id, data)
    return _update_user_info_mem(user_id, data)


def _update_user_info_mem(user_id: str, data: dict) -> dict:
    user = USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    allowed_fields = ["nickname", "bio", "birthday", "music_taste", "avatar"]
    for field in allowed_fields:
        if field in data and data[field] is not None:
            user[field] = data[field]

    return {
        "user_id": str(user.get("user_id")),
        "nickname": user.get("nickname"),
        "bio": user.get("bio"),
        "birthday": user.get("birthday"),
        "music_taste": user.get("music_taste"),
        "avatar": user.get("avatar"),
    }


def _update_user_info_db(user_id: str, data: dict) -> dict:
    """更新数据库中的用户信息"""
    from backend.db.models import User

    session = _get_session()
    try:
        user = session.get(User, int(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        # 批量更新字段
        allowed_fields = ["nickname", "bio", "birthday", "music_taste", "avatar"]
        for field in allowed_fields:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])

        session.commit()
        return {
            "user_id": str(user.id),
            "nickname": user.nickname,
            "bio": user.bio,
            "birthday": user.birthday,
            "music_taste": user.music_taste,
            "avatar": user.avatar,
        }
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


# ===== current user from header =====
def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_by_token(token)


# ===== logout =====
def logout_user(token: str) -> dict:
    if USE_DB:
        return _logout_user_db(token)
    return _logout_user_mem(token)


def _logout_user_mem(token: str) -> dict:
    if token not in TOKENS:
        raise HTTPException(status_code=400, detail="token not exists")
    del TOKENS[token]
    return {"message": "logged out"}


def _logout_user_db(token: str) -> dict:
    from backend.db.models import UserToken
    session = _get_session()
    try:
        tok = session.query(UserToken).filter_by(token=token).first()
        if not tok:
            raise HTTPException(status_code=400, detail="token not exists")
        session.delete(tok)
        session.commit()
        return {"message": "logged out"}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ===== preferences =====
PREFERENCES: dict[str, dict] = {}

_DEFAULT_PREFERENCES = {
    "audio_engine": "default",
    "export_formats": ["MIDI", "PNG", "PDF"],
}


def get_preferences(user_id: str) -> dict:
    if USE_DB:
        return _get_preferences_db(user_id)
    return _get_preferences_mem(user_id)


def _get_preferences_mem(user_id: str) -> dict:
    return {**_DEFAULT_PREFERENCES, **PREFERENCES.get(user_id, {})}


def _get_preferences_db(user_id: str) -> dict:
    from backend.db.models import UserPreference
    session = _get_session()
    try:
        row = session.query(UserPreference).filter_by(user_id=int(user_id)).first()
        if not row:
            return {**_DEFAULT_PREFERENCES}
        return {**_DEFAULT_PREFERENCES, **(row.preferences or {})}
    finally:
        session.close()


def update_preferences(user_id: str, prefs: dict) -> dict:
    if USE_DB:
        return _update_preferences_db(user_id, prefs)
    return _update_preferences_mem(user_id, prefs)


def _update_preferences_mem(user_id: str, prefs: dict) -> dict:
    current = PREFERENCES.get(user_id, {})
    current.update(prefs)
    PREFERENCES[user_id] = current
    return {**_DEFAULT_PREFERENCES, **current}


def _update_preferences_db(user_id: str, prefs: dict) -> dict:
    from backend.db.models import UserPreference
    session = _get_session()
    try:
        row = session.query(UserPreference).filter_by(user_id=int(user_id)).first()
        if row:
            merged = {**(row.preferences or {}), **prefs}
            row.preferences = merged
        else:
            merged = {**_DEFAULT_PREFERENCES, **prefs}
            row = UserPreference(user_id=int(user_id), preferences=merged)
            session.add(row)
        session.commit()
        return {**_DEFAULT_PREFERENCES, **merged}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()