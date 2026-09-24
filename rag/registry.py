"""文档注册表：SQLite 记录入库文档的元信息（纯标准库实现）"""

import sqlite3
import threading
from typing import Optional

from .config import settings
from .schemas import DocInfo


class DocumentRegistry:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or settings.registry_db)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id     TEXT PRIMARY KEY,
                filename   TEXT NOT NULL,
                pages      INTEGER,
                chunks     INTEGER,
                chars      INTEGER,
                added_at   REAL,
                status     TEXT DEFAULT 'active'
            )""")
        self._conn.commit()

    def add(self, doc: DocInfo) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?)",
                (doc.doc_id, doc.filename, doc.pages, doc.chunks,
                 doc.chars, doc.added_at, doc.status),
            )
            self._conn.commit()

    def mark_deleted(self, doc_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET status='deleted' WHERE doc_id=?", (doc_id,)
            )
            self._conn.commit()

    def find_active_by_filename(self, filename: str) -> Optional[DocInfo]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc_id, filename, pages, chunks, chars, added_at, status "
                "FROM documents WHERE filename=? AND status='active'", (filename,)
            ).fetchone()
        return DocInfo(**dict(zip(
            ["doc_id", "filename", "pages", "chunks", "chars", "added_at", "status"],
            row))) if row else None

    def list_active(self) -> list[DocInfo]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT doc_id, filename, pages, chunks, chars, added_at, status "
                "FROM documents WHERE status='active' ORDER BY added_at DESC"
            ).fetchall()
        keys = ["doc_id", "filename", "pages", "chunks", "chars", "added_at", "status"]
        return [DocInfo(**dict(zip(keys, r))) for r in rows]

    def get(self, doc_id: str) -> Optional[DocInfo]:
        with self._lock:
            row = self._conn.execute(
                "SELECT doc_id, filename, pages, chunks, chars, added_at, status "
                "FROM documents WHERE doc_id=? AND status='active'", (doc_id,)
            ).fetchone()
        if not row:
            return None
        keys = ["doc_id", "filename", "pages", "chunks", "chars", "added_at", "status"]
        return DocInfo(**dict(zip(keys, row)))
