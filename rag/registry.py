"""文档注册表：SQLite 记录入库文档的元信息与案例元数据（纯标准库实现）"""

import sqlite3
import threading
from typing import Optional

from .config import settings
from .schemas import CaseMeta, DocInfo

# 基础列 + 案例元数据列（案例 5 列对应 CaseMeta 字段）
_COLS = ["doc_id", "filename", "pages", "chunks", "chars",
         "added_at", "status", "case_title", "course", "case_type",
         "knowledge_points", "related_theory"]

_CASE_COLS = _COLS[7:]


def _row_to_doc(row: tuple) -> DocInfo:
    d = dict(zip(_COLS, row))
    case = CaseMeta(
        case_title=d["case_title"] or "",
        course=d["course"] or "",
        case_type=d["case_type"] or "",
        knowledge_points=d["knowledge_points"] or "",
        related_theory=d["related_theory"] or "",
    )
    d["case"] = None if case.is_empty() else case
    for col in _CASE_COLS:
        d.pop(col)
    return DocInfo(**d)


class DocumentRegistry:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or settings.registry_db)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id           TEXT PRIMARY KEY,
                filename         TEXT NOT NULL,
                pages            INTEGER,
                chunks           INTEGER,
                chars            INTEGER,
                added_at         REAL,
                status           TEXT DEFAULT 'active',
                case_title       TEXT DEFAULT '',
                course           TEXT DEFAULT '',
                case_type        TEXT DEFAULT '',
                knowledge_points TEXT DEFAULT '',
                related_theory   TEXT DEFAULT ''
            )""")
        self._migrate_legacy()
        self._conn.commit()

    def _migrate_legacy(self) -> None:
        """旧版库（无案例列）自动补列，保持向后兼容"""
        for col in _CASE_COLS:
            try:
                self._conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在

    def add(self, doc: DocInfo) -> None:
        case = doc.case or CaseMeta()
        values = [doc.doc_id, doc.filename, doc.pages, doc.chunks,
                  doc.chars, doc.added_at, doc.status,
                  case.case_title, case.course, case.case_type,
                  case.knowledge_points, case.related_theory]
        with self._lock:
            self._conn.execute(
                f"INSERT OR REPLACE INTO documents VALUES ({','.join('?' * len(_COLS))})",
                values,
            )
            self._conn.commit()

    def mark_deleted(self, doc_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET status='deleted' WHERE doc_id=?", (doc_id,)
            )
            self._conn.commit()

    def _select_one(self, sql: str, params: tuple) -> Optional[DocInfo]:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return _row_to_doc(row) if row else None

    def find_active_by_filename(self, filename: str) -> Optional[DocInfo]:
        cols = ",".join(_COLS)
        return self._select_one(
            f"SELECT {cols} FROM documents WHERE filename=? AND status='active'",
            (filename,),
        )

    def list_active(self) -> list[DocInfo]:
        cols = ",".join(_COLS)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {cols} FROM documents WHERE status='active' ORDER BY added_at DESC"
            ).fetchall()
        return [_row_to_doc(r) for r in rows]

    def get(self, doc_id: str) -> Optional[DocInfo]:
        cols = ",".join(_COLS)
        return self._select_one(
            f"SELECT {cols} FROM documents WHERE doc_id=? AND status='active'",
            (doc_id,),
        )
