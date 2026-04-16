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
            username=username_in,
            password=_hash_password(password_in),
            email=email_in,
            create_time=datetime.now(timezone.utc)
        )
        db.add(new_user) # 使用 db.add
        # 不需要 commit()，with 块退出时会自动提交
        
    return {
        "code": 0,
        "message": "success",
        "data": {"user_id": user_id}
    }

# 登录函数
def login_user(username_in: str, password: str) -> dict:
    user_data = None
    token = ""
    
    with session_scope() as db:
        myuser = db.query(User).filter_by(username=username_in).first()
        if not myuser:
            raise HTTPException(status_code=400, detail="username not exists")
        if myuser.password != _hash_password(password):
            raise HTTPException(status_code=400, detail="incorrect password")
        
        token = f"tok_{uuid4().hex}"
        expired_time = datetime.now(timezone.utc) + timedelta(seconds=7200)

        myuser_token = UserToken(
            token=token,
            user_id=myuser.id, 
            expired_time=expired_time
        )

        db.add(myuser_token)
        user_data = {
            "user_id": myuser.id, 
            "username": myuser.username
        }
    
    return {
            "code": 0,
            "message": "success",
            "data": {
                "token": token,
                "expires_in": 7200,
                "user": user_data
            }
    }

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
