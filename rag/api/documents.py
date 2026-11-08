"""案例路由：列表 / 上传 / 批量导入 / 元数据编辑 / 删除 / 原文重组 / 语义检索
（任务书模块2、3、4）"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_teacher
from ..database import Document, Topic, User, get_db, log_audit
from ..pipeline import get_pipeline
from ..schemas import CaseMeta

router = APIRouter(prefix="/api/documents", tags=["案例库"])


def _dump(row: Document, topic_name: str = "") -> dict:
    return {
        "doc_id": row.doc_id, "filename": row.filename,
        "pages": row.pages, "chunks": row.chunks, "chars": row.chars,
        "added_at": row.added_at.isoformat(), "status": row.status,
        "case": {
            "case_title": row.case_title, "course": row.course,
            "case_type": row.case_type,
            "knowledge_points": row.knowledge_points,
            "related_theory": row.related_theory,
        } if row.case_title else None,
        "source_info": row.source_info,
        "topic_id": row.topic_id, "topic_name": topic_name,
        "uploader_id": row.uploader_id,
    }


def _rows_with_topic(db: Session, rows: list[Document]) -> list[dict]:
    tmap = {t.id: t.name for t in db.scalars(select(Topic)).all()}
    return [_dump(r, tmap.get(r.topic_id, "")) for r in rows]


@router.get("")
def list_documents(topic_id: Optional[int] = None, q: str = "",
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """案例列表（支持专题过滤与文件名/案例名模糊搜索）"""
    stmt = select(Document).where(Document.status == "active")
    if topic_id:
        stmt = stmt.where(Document.topic_id == topic_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Document.filename.like(like)
                          | Document.case_title.like(like)
                          | Document.knowledge_points.like(like))
    rows = db.scalars(stmt.order_by(Document.added_at.desc())).all()
    return _rows_with_topic(db, rows)


@router.post("/upload")
async def upload(file: UploadFile = File(...), topic_id: Optional[int] = None,
                db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    """单案例上传（PDF/DOCX/TXT/MD，自动解析切片与元数据，全程留痕）"""
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    data = await file.read()
    result = get_pipeline().ingest(data, file.filename,
                                   topic_id=topic_id, uploader_id=user.id)
    if not result.success:
        raise HTTPException(422, result.message)
    log_audit(db, user.id, "document_upload", "document",
              result.doc_id, file.filename)
    db.commit()
    return result.model_dump()


@router.post("/batch")
async def batch_upload(files: list[UploadFile] = File(...),
                       topic_id: Optional[int] = None,
                       db: Session = Depends(get_db),
                       user: User = Depends(require_teacher)):
    """多案例批量导入：逐个处理，单个失败不中断"""
    pipeline = get_pipeline()
    results = []
    for f in files:
        if not f.filename:
            continue
        data = await f.read()
        r = pipeline.ingest(data, f.filename, topic_id=topic_id,
                            uploader_id=user.id)
        if r.success:
            log_audit(db, user.id, "document_upload", "document",
                      r.doc_id, f.filename)
            results.append({"filename": f.filename, "success": True,
                            "doc_id": r.doc_id, "message": r.message})
        else:
            results.append({"filename": f.filename, "success": False,
                            "doc_id": r.doc_id, "message": r.message})
    db.commit()
    return {"count": len(results), "success_count":
            sum(1 for r in results if r["success"]), "results": results}


class MetaBody(BaseModel):
    case_title: str = ""
    course: str = ""
    case_type: str = ""
    knowledge_points: str = ""
    related_theory: str = ""
    source_info: str = ""
    topic_id: Optional[int] = None


@router.put("/{doc_id}/meta")
def update_meta(doc_id: str, body: MetaBody, db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    """元数据编辑（案例信息 / 来源信息 / 专题归属，留痕）"""
    pipeline = get_pipeline()
    case = CaseMeta(case_title=body.case_title, course=body.course,
                    case_type=body.case_type,
                    knowledge_points=body.knowledge_points,
                    related_theory=body.related_theory)
    if not pipeline.registry.update_meta(doc_id, case, body.source_info,
                                         body.topic_id, user.id):
        raise HTTPException(404, "案例不存在")
    log_audit(db, user.id, "document_meta_update", "document", doc_id,
              f"案例：{body.case_title}")
    db.commit()
    row = db.get(Document, doc_id)
    return _dump(row)


@router.delete("/{doc_id}")
def delete_document(doc_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_teacher)):
    """删除案例（向量库/索引同步清理，注册表软删，留痕）"""
    if not get_pipeline().delete_document(doc_id):
        raise HTTPException(404, "案例不存在")
    log_audit(db, user.id, "document_delete", "document", doc_id, "")
    db.commit()
    return {"success": True, "message": "案例已删除"}


@router.get("/{doc_id}/content")
def read_content(doc_id: str, user: User = Depends(get_current_user)):
    """案例原文重组（按 chunk_index 拼接切片，供在线阅读）"""
    info = get_pipeline().registry.get(doc_id)
    if not info:
        raise HTTPException(404, "案例不存在")
    chunks = sorted((c for c in get_pipeline().vs.get_all_chunks()
                     if c.doc_id == doc_id), key=lambda c: c.chunk_index)
    return {
        "doc_id": doc_id, "filename": info.filename,
        "case": info.case.model_dump() if info.case else None,
        "chunks": [{"chunk_id": c.chunk_id, "page": c.page,
                    "index": c.chunk_index, "content": c.content}
                   for c in chunks],
    }
