"""检索与答疑路由：语义检索 / 流式答疑 / 我的答疑记录（任务书模块4、6）

每次答疑完成后写入 qa_records（AI 原始输出落库，供教师审核纠错）。
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import QARecord, User, get_db, dumps_citations
from ..pipeline import get_pipeline
from ..schemas import AskOptions

router = APIRouter(prefix="/api", tags=["检索与答疑"])


@router.get("/cases/search")
def search_cases(q: str, k: int = 4, topic_id: Optional[int] = None,
                 user: User = Depends(get_current_user)):
    """语义检索案例片段（混合检索，支持按专题过滤命中结果）"""
    if not q.strip():
        raise HTTPException(400, "请输入检索内容")
    pipeline = get_pipeline()
    hits = pipeline.retrieve(q, k=k)
    if topic_id:
        doc_ids = {d.doc_id for d in pipeline.registry.list_by_topic(topic_id)}
        hits = [h for h in hits if h.chunk.doc_id in doc_ids]
    out = []
    for h in hits:
        c = h.chunk
        out.append({
            "chunk_id": c.chunk_id, "doc_id": c.doc_id,
            "filename": c.filename, "page": c.page,
            "score": round(h.score, 4), "stage": h.stage,
            "content": c.content,
            "case_title": c.case_title, "course": c.course,
            "case_type": c.case_type, "knowledge_points": c.knowledge_points,
        })
    return {"query": q, "count": len(out), "hits": out}


class ChatBody(BaseModel):
    question: str
    session_id: Optional[str] = None
    stream: bool = False
    retrieval_mode: Optional[str] = None
    use_rerank: Optional[bool] = None
    top_k: Optional[int] = None


def _save_record(db: Session, user: User, question: str, answer: str,
                 sources: list) -> int:
    """答疑结果落库（教师审核纠错的对象）"""
    rec = QARecord(record_type="answer", question=question,
                   ai_content=answer, citations=json.loads(
                       dumps_citations(sources) or "[]"),
                   student_id=user.id)
    db.add(rec)
    db.commit()
    return rec.id


@router.post("/chat")
def chat(body: ChatBody, db: Session = Depends(get_db),
         user: User = Depends(get_current_user)):
    """案例研习答疑（SSE 流式；完成后写 qa_records）"""
    if not body.question.strip():
        raise HTTPException(400, "请输入问题")
    options = AskOptions(retrieval_mode=body.retrieval_mode,
                         use_rerank=body.use_rerank, top_k=body.top_k)

    if not body.stream:
        result = get_pipeline().ask(body.question, options, body.session_id)
        if result.success:
            record_id = _save_record(db, user, body.question,
                                     result.answer, result.sources)
        else:
            record_id = None
        data = result.model_dump()
        data["record_id"] = record_id
        return data

    def sse():
        answer, sources = "", []
        try:
            for event in get_pipeline().ask_stream(
                    body.question, options, body.session_id):
                if event.get("type") == "sources":
                    sources = event.get("sources", [])
                if event.get("type") == "done":
                    answer = event.get("answer", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if answer:
                rid = _save_record(db, user, body.question, answer, sources)
                yield f"data: {json.dumps({'type': 'record', 'record_id': rid}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 — SSE 需要把错误推给前端
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _record_view(r: QARecord, student_name: str = "") -> dict:
    return {
        "id": r.id, "record_type": r.record_type,
        "question": r.question,
        "ai_content": r.ai_content,
        "final_content": r.final_content,  # 教师修正稿（学生端展示此稿）
        "citations": r.citations or [],
        "student_id": r.student_id, "student_name": student_name,
        "doc_id": r.doc_id, "status": r.status,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/my/records")
def my_records(db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """学生查看自己的答疑记录（教师修正后以 final_content 为准）"""
    rows = db.scalars(select(QARecord).where(
        QARecord.student_id == user.id,
        QARecord.record_type == "answer",
    ).order_by(QARecord.id.desc()).limit(100)).all()
    return [_record_view(r) for r in rows]


@router.post("/sessions")
def new_session():
    """新建多轮会话"""
    return {"session_id": get_pipeline().sessions.new_session()}
