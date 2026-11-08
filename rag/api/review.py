"""教师审核纠错路由（任务书模块7，已按要求去掉驳回功能）

教师可查看 AI 生成的引导问题与答疑结果，修改生成内容、补充批注，
纠错修改动作全程留痕（review_logs 追加只写，ai_content 不可变）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import QARecord, ReviewLog, User, get_db, log_audit
from ..pipeline import get_pipeline

router = APIRouter(prefix="/api/review", tags=["教师审核"])

# 复用 chat 模块的记录视图
from .chat import _record_view  # noqa: E402


@router.get("/records")
def list_records(status: Optional[str] = None,
                 record_type: Optional[str] = None,
                 db: Session = Depends(get_db),
                 user: User = Depends(require_teacher)):
    """审核列表（按状态/类型筛选）"""
    stmt = select(QARecord)
    if status:
        stmt = stmt.where(QARecord.status == status)
    if record_type:
        stmt = stmt.where(QARecord.record_type == record_type)
    rows = db.scalars(stmt.order_by(QARecord.id.desc()).limit(200)).all()
    ids = [r.id for r in rows]
    names = dict(db.execute(
        select(User.id, User.username).where(User.id.in_(
            {r.student_id for r in rows} - {None}))).all()) if ids else {}
    out = []
    for r in rows:
        v = _record_view(r, names.get(r.student_id, ""))
        v.pop("ai_content", None)  # 列表不带正文，详情再看
        out.append(v)
    return out


@router.get("/records/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    """审核详情：问题 + AI 原稿 + 修正稿 + 引用来源对照"""
    r = db.get(QARecord, record_id)
    if not r:
        raise HTTPException(404, "记录不存在")
    sname = db.scalar(select(User.username).where(User.id == r.student_id)) or ""
    return _record_view(r, sname)


class EditBody(BaseModel):
    content: str  # 教师修正后的完整内容


class CommentBody(BaseModel):
    comment: str  # 批注内容


def _log(db: Session, rec: QARecord, teacher_id: int, action: str,
         before: str, after: str):
    db.add(ReviewLog(record_id=rec.id, teacher_id=teacher_id,
                     action=action, content_before=before or "",
                     content_after=after or ""))


@router.put("/records/{record_id}")
def edit_record(record_id: int, body: EditBody,
                db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    """修改 AI 生成内容：原稿不动，修正稿写入 final_content，留痕"""
    r = db.get(QARecord, record_id)
    if not r:
        raise HTTPException(404, "记录不存在")
    before = r.final_content or r.ai_content
    r.final_content = body.content
    r.status = "corrected"
    _log(db, r, user.id, "edit", before, body.content)
    db.commit()
    return _record_view(r)


@router.post("/records/{record_id}/comment")
def comment_record(record_id: int, body: CommentBody,
                   db: Session = Depends(get_db),
                   user: User = Depends(require_teacher)):
    """补充批注：不改内容，追加教师点评，留痕"""
    r = db.get(QARecord, record_id)
    if not r:
        raise HTTPException(404, "记录不存在")
    if r.status == "pending":
        r.status = "annotated"
    _log(db, r, user.id, "comment", "", body.comment)
    db.commit()
    return _record_view(r)


@router.get("/records/{record_id}/logs")
def record_logs(record_id: int, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    """留痕时间线：这条记录的全部纠错动作"""
    r = db.get(QARecord, record_id)
    if not r:
        raise HTTPException(404, "记录不存在")
    rows = db.scalars(select(ReviewLog).where(
        ReviewLog.record_id == record_id).order_by(ReviewLog.id)).all()
    tmap = dict(db.execute(select(User.id, User.username)).all())
    return [{
        "id": lg.id, "action": lg.action,
        "teacher": tmap.get(lg.teacher_id, str(lg.teacher_id)),
        "content_before": lg.content_before, "content_after": lg.content_after,
        "created_at": lg.created_at.isoformat(),
    } for lg in rows]


# ── 研习引导问题生成（任务书模块5，生成后进审核队列）──

from pydantic import BaseModel as _BM  # noqa: E402

class GuideBody(_BM):
    doc_id: str
    n: int = 5


@router.post("/guide-questions")
def generate_guide(body: GuideBody, db: Session = Depends(get_db),
                  user: User = Depends(require_teacher)):
    """对指定案例生成课堂研习引导问题（AI 原稿落库，可修改/批注）"""
    result = get_pipeline().generate_guide_questions(body.doc_id, body.n)
    if not result.get("success"):
        raise HTTPException(422, result.get("message", "生成失败"))
    # 每道问题合成一份可审核文稿
    lines = [f"案例《{result['case_title']}》研习引导问题：", ""]
    for i, q in enumerate(result["questions"], start=1):
        lines.append(f"{i}. {q['question']}（关联资料 {q['ref']}）")
    content = "\n".join(lines)
    rec = QARecord(record_type="guide_q",
                   question=f"案例《{result['case_title']}》引导问题",
                   ai_content=content, doc_id=body.doc_id)
    db.add(rec)
    db.commit()
    log_audit(db, user.id, "guide_question_generate", "document",
              body.doc_id, result["case_title"])
    db.commit()
    return {"success": True, "record_id": rec.id,
            "case_title": result["case_title"], "content": content,
            "questions": result["questions"]}
