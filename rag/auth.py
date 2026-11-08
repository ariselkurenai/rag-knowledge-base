"""认证与权限：bcrypt 密码哈希 + PyJWT 令牌 + FastAPI 角色依赖

角色模型（任务书"教师与学生管理员两类"的实现口径）：
- student  学生类：检索、阅读、提问、查看自己的答疑记录
- teacher  教师类：上传/管理案例、生成引导问题、审核纠错
- admin    管理职责（教师类中的管理角色）：用户管理、专题管理
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import User, get_db

_bearer = HTTPBearer(auto_error=False)


# ── 密码 ──

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ── JWT ──

def create_token(user: User) -> str:
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """无效/过期令牌抛 HTTPException 401"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的登录凭证")


# ── FastAPI 依赖 ──

def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
                     db: Session = Depends(get_db)) -> User:
    """解析 Bearer 令牌，返回当前用户（未登录 401）"""
    if cred is None:
        raise HTTPException(401, "未登录")
    payload = decode_token(cred.credentials)
    user = db.get(User, payload.get("user_id"))
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def require_role(*roles: str):
    """角色校验依赖工厂：require_role("teacher", "admin")"""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"需要 {' / '.join(roles)} 权限")
        return user
    return checker


# 教师类（含管理职责的 admin）
require_teacher = require_role("teacher", "admin")
# 仅管理员
require_admin = require_role("admin")
