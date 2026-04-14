from __future__ import annotations
"""Simple in-memory auth/user system."""
from backend.database.models import user,usertoken
from backend.database.db import db


import hashlib
from datetime import datetime, timezone,timedelta
from uuid import uuid4

from fastapi import Header, HTTPException


#密码加密处理函数
def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


#注册函数
def register_user(username_in: str, password_in: str, email_in: str | None = None) -> dict:
    if user.query.filter_by(username=username_in).first():
        raise HTTPException(status_code=400,detial="username already exists")
    
    user_id=f"u_{uuid4().hex[:8]}"
    new_user=user(
        id=user_id,
        username=username_in,
        password=_hash_password(password_in),
        email=email_in,
        create_time=datetime.now(timezone.utc)
        )
    db.session.add(new_user)
    db.session.commit()
    return {
        "code": 0,
        "message": "success",
        "data": {
            "user_id": user_id
        }
    }



#登录函数
def login_user(username_in: str, password: str) -> dict:
    myuser=user.query.filter_by(username=username_in).first()
    if not myuser:
        raise HTTPException(status_code=400,detail="username not exists")
    if myuser.password!=_hash_password(password):
        raise HTTPException(status_code=400,detail="incorrect password")
    
    token=f"tok_{uuid4().hex}"
    expired_time = datetime.now(timezone.utc) + timedelta(seconds=7200)

    myuser_token=usertoken(token=token,id=myuser.id,expired_time=expired_time)

    db.seesion.add(myuser_token)
    db.seesion.commit()

    return  {
            "code": 0,
            "message": "success",
            "data": {
                "token": token,
                "expires_in": 7200,
                "user": {
                    "user_id": myuser.id,
                    "username": myuser.username
                        }
                    }
            }

#通过token快速获取userid
def get_user_by_token(token: str) -> dict:
    now_time=datetime.now(timezone.utc)
    token_record=usertoken.query.filter(usertoken.token==token,usertoken.expired_time>now_time).first()

    if not token_record:
        raise HTTPException(status_code=401,detail="token invalid or expired")
    myuser=user.query.get(token_record.id)
    return  {
        "user_id":myuser.user_id,
        "username":myuser.username,
        "email":myuser.email
    }

#所有需要登录功能使用前对登陆状态的安全验证：验证token是否有效
def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    return get_user_by_token(token)

# 退出登录函数：让token立即失效
def logout_user(token: str):
    token_record = usertoken.query.filter_by(token=token).first()
    
    if not token_record:
        raise HTTPException(status_code=400, detail="token not exists")
    
    db.session.delete(token_record)
    db.session.commit()
    
    return {"message": "退出登录成功,token已失效"}