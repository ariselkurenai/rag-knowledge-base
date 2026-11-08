"""用户管理路由（仅管理员）：列表 / 角色调整（留痕）"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import QARecord, User, get_db, log_audit

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("")
def list_users(db: Session = Depends(get_db),
               user: User = Depends(require_admin)):
    rows = db.scalars(select(User).order_by(User.id)).all()
    counts = dict(db.execute(
        select(QARecord.student_id, func.count(QARecord.id))
        .group_by(QARecord.student_id)).all())
    return [{
        "id": u.id, "username": u.username, "role": u.role,
        "created_at": u.created_at.isoformat(),
        "record_count": counts.get(u.id, 0),
    } for u in rows]


class RoleBody(BaseModel):
    role: str  # admin / teacher / student


@router.put("/{user_id}/role")
def change_role(user_id: int, body: RoleBody,
                db: Session = Depends(get_db),
                user: User = Depends(require_admin)):
    if body.role not in ("admin", "teacher", "student"):
        raise HTTPException(422, "角色必须是 admin / teacher / student")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    if target.id == user.id:
        raise HTTPException(409, "不能修改自己的角色")
    old = target.role
    target.role = body.role
    log_audit(db, user.id, "user_role_change", "user", user_id,
              f"{target.username}: {old} → {body.role}")
    db.commit()
    return {"success": True, "message": f"{target.username} 角色已改为 {body.role}"}
