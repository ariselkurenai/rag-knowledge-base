"""文档注册表：MySQL 版（SQLAlchemy ORM）

对外接口与旧 SQLite 版保持一致（add / mark_deleted / get /
find_active_by_filename / list_active），pipeline 无感切换。
新增：update_meta（元数据/专题/来源编辑）、list_by_topic。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from .database import Document, SessionLocal
from .schemas import CaseMeta, DocInfo


def _to_doc(row: Document) -> DocInfo:
    case = CaseMeta(
        case_title=row.case_title or "",
        course=row.course or "",
        case_type=row.case_type or "",
        knowledge_points=row.knowledge_points or "",
        related_theory=row.related_theory or "",
    )
    added = row.added_at
    ts = added.replace(tzinfo=timezone.utc).timestamp() if isinstance(
        added, datetime) else float(added or 0)
    return DocInfo(
        doc_id=row.doc_id, filename=row.filename,
        pages=row.pages, chunks=row.chunks, chars=row.chars,
        added_at=ts, status=row.status,
        case=None if case.is_empty() else case,
        source_info=row.source_info or "",
        topic_id=row.topic_id, uploader_id=row.uploader_id,
    )


class DocumentRegistry:
    """每次调用独立短会话（连接池复用），天然线程安全。

    session_factory 仅测试用（注入指向测试库的会话工厂）；
    生产环境留空使用默认 SessionLocal。
    """

    def __init__(self, session_factory=None):
        self._Session = session_factory or SessionLocal

    def add(self, doc: DocInfo) -> None:
        case = doc.case or CaseMeta()
        db = self._Session()
        try:
            db.merge(Document(
                doc_id=doc.doc_id, filename=doc.filename,
                pages=doc.pages, chunks=doc.chunks, chars=doc.chars,
                status=doc.status,
                case_title=case.case_title, course=case.course,
                case_type=case.case_type,
                knowledge_points=case.knowledge_points,
                related_theory=case.related_theory,
                source_info=doc.source_info,
                topic_id=doc.topic_id, uploader_id=doc.uploader_id,
            ))
            db.commit()
        finally:
            db.close()

    def mark_deleted(self, doc_id: str) -> None:
        db = self._Session()
        try:
            row = db.get(Document, doc_id)
            if row:
                row.status = "deleted"
                db.commit()
        finally:
            db.close()

    def get(self, doc_id: str) -> Optional[DocInfo]:
        db = self._Session()
        try:
            row = db.scalar(select(Document).where(
                Document.doc_id == doc_id, Document.status == "active"))
            return _to_doc(row) if row else None
        finally:
            db.close()

    def find_active_by_filename(self, filename: str) -> Optional[DocInfo]:
        db = self._Session()
        try:
            row = db.scalar(select(Document).where(
                Document.filename == filename, Document.status == "active"))
            return _to_doc(row) if row else None
        finally:
            db.close()

    def list_active(self) -> list[DocInfo]:
        db = self._Session()
        try:
            rows = db.scalars(select(Document).where(
                Document.status == "active"
            ).order_by(Document.added_at.desc())).all()
            return [_to_doc(r) for r in rows]
        finally:
            db.close()

    # ── 新增：案例元数据/专题管理 ──

    def update_meta(self, doc_id: str, case: CaseMeta,
                    source_info: str = "", topic_id: Optional[int] = None,
                    uploader_id: Optional[int] = None) -> bool:
        """教师端元数据编辑：更新案例 5 列 + 来源信息 + 专题归属"""
        db = self._Session()
        try:
            row = db.get(Document, doc_id)
            if not row or row.status != "active":
                return False
            if case.case_title: row.case_title = case.case_title
            if case.course: row.course = case.course
            if case.case_type: row.case_type = case.case_type
            if case.knowledge_points: row.knowledge_points = case.knowledge_points
            if case.related_theory: row.related_theory = case.related_theory
            if source_info: row.source_info = source_info
            row.topic_id = topic_id
            if uploader_id is not None:
                row.uploader_id = uploader_id
            db.commit()
            return True
        finally:
            db.close()

    def set_topic(self, doc_id: str, topic_id: Optional[int]) -> bool:
        db = self._Session()
        try:
            row = db.get(Document, doc_id)
            if not row:
                return False
            row.topic_id = topic_id
            db.commit()
            return True
        finally:
            db.close()

    def list_by_topic(self, topic_id: int) -> list[DocInfo]:
        db = self._Session()
        try:
            rows = db.scalars(select(Document).where(
                Document.topic_id == topic_id,
                Document.status == "active",
            ).order_by(Document.added_at.desc())).all()
            return [_to_doc(r) for r in rows]
        finally:
            db.close()
