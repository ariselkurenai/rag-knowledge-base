"""专题路由：思政课程专题案例库管理（任务书模块3）

读取：登录用户；增删改：教师类（teacher/admin）。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import Document, Topic, User, get_db, log_audit

router = APIRouter(prefix="/api/topics", tags=["专题"])


def _dump(t: Topic, count: int = 0) -> dict:
    return {"id": t.id, "name": t.name, "description": t.description,
            "created_at": t.created_at.isoformat(), "case_count": count}


@router.get("")
def list_topics(db: Session = Depends(get_db)):
    rows = db.scalars(select(Topic).order_by(Topic.id)).all()
    out = []
    for t in rows:
        n = len(db.scalars(select(Document.doc_id).where(
            Document.topic_id == t.id, Document.status == "active")).all())
        out.append(_dump(t, n))
    return out


class TopicBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = ""


@router.post("")
def create_topic(body: TopicBody, db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    if db.scalar(select(Topic).where(Topic.name == body.name)):
        raise HTTPException(409, "专题名称已存在")
    t = Topic(name=body.name, description=body.description)
    db.add(t)
    db.flush()
    log_audit(db, user.id, "topic_create", "topic", t.id, body.name)
    db.commit()
    return _dump(t)


@router.put("/{topic_id}")
def update_topic(topic_id: int, body: TopicBody,
                 db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404, "专题不存在")
    old = t.name
    t.name, t.description = body.name, body.description
    log_audit(db, user.id, "topic_update", "topic", t.id, f"{old} → {body.name}")
    db.commit()
    return _dump(t)


@router.delete("/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404, "专题不存在")
    n = db.scalars(select(Document.doc_id).where(
        Document.topic_id == topic_id, Document.status == "active")).all()
    if n:
        raise HTTPException(409, f"专题下仍有 {len(n)} 个案例，请先移出")
    db.delete(t)
    log_audit(db, user.id, "topic_delete", "topic", topic_id, t.name)
    db.commit()
    return {"success": True, "message": "专题已删除"}
