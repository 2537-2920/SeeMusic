from __future__ import annotations
"""Simple in-memory auth/user system."""
from backend.db.models import User, UserToken
from backend.db.session import session_scope # 统一使用这个来操作数据库
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import Header, HTTPException

# 密码加密处理函数
def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# 注册函数
def register_user(username_in: str, password_in: str, email_in: str | None = None) -> dict:
    with session_scope() as db: # 开启数据库会话
        if db.query(User).filter_by(username=username_in).first():
            raise HTTPException(status_code=400, detail="username already exists")
    
        user_id = f"u_{uuid4().hex[:8]}"
        new_user = User(
            password=_hash_password(password_in),
            email=email_in,
            create_time=datetime.now(timezone.utc)
        )
        db.add(new_user) # 使用 db.add
        # 不需要 commit()，with 块退出时会自动提交
        


# 通过token快速获取userid
def get_user_by_token(token: str) -> dict:
    now_time = datetime.now(timezone.utc)
    with session_scope() as db:
        token_record = db.query(UserToken).filter(UserToken.token == token, UserToken.expired_time > now_time).first()
        if not token_record:
            raise HTTPException(status_code=401, detail="token invalid or expired")
        
        myuser = db.query(User).get(token_record.id)
        if not myuser:
            raise HTTPException(status_code=401, detail="user not found")
            
        return {
            "user_id": myuser.id, # 确保字段名是 id 还是 user_id
            "username": myuser.username,
            "email": myuser.email
        }

# 退出登录函数
def logout_user(token: str):
    with session_scope() as db:
        token_record = db.query(UserToken).filter_by(token=token).first()
        if not token_record:
            raise HTTPException(status_code=400, detail="token not exists")
        
        db.delete(token_record) # 使用 db.delete
        # 自动 commit
    
    return {"message": "退出登录成功,token已失效"}

#所有需要登录功能使用前对登陆状态的安全验证：验证token是否有效
def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_by_token(token)
<<<<<<< HEAD


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
=======
>>>>>>> 9f15fe82e422c3f2cb326c055ffe04f096de512e
