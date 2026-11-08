"""认证路由：学生注册 / 登录 / 当前用户（任务书模块1）"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, hash_password, verify_password
from ..database import User, get_db

router = APIRouter(prefix="/api/auth", tags=["认证"])


class RegisterBody(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=64)


class LoginBody(RegisterBody):
    pass


@router.post("/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    """学生自助注册（角色固定 student，教师/管理员由管理员配置）"""
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "用户名已存在")
    user = User(username=body.username,
                password_hash=hash_password(body.password), role="student")
    db.add(user)
    db.commit()
    return {"success": True, "message": "注册成功，请登录",
            "user": {"id": user.id, "username": user.username, "role": user.role}}


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"success": True,
            "token": create_token(user),
            "user": {"id": user.id, "username": user.username, "role": user.role}}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
