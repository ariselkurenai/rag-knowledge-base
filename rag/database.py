"""MySQL 数据层：SQLAlchemy ORM 模型 + 引擎 + 操作留痕

存储内容（任务书要求）：
- 用户信息（users，三角色 admin/teacher/student）
- 专题信息（topics，2 个思政课程专题案例库）
- 案例元数据（documents，替代旧 SQLite 注册表）
- 答疑记录与引导问题（qa_records，AI 原始输出不可变）
- 教师纠错记录（review_logs，追加只写，全程留痕）
- 通用操作审计（audit_logs，案例上传/修改/删除、角色变更等）

留痕机制：qa_records.ai_content 永不覆盖，教师修改写 final_content；
每次审核动作追加一条 review_logs；通用操作追加 audit_logs。
"""

import json
from datetime import datetime

from sqlalchemy import (JSON, DateTime, Enum, ForeignKey, Integer,
                        String, Text, create_engine)
from sqlalchemy.dialects.mysql import MEDIUMTEXT as MediumText
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            sessionmaker)

from .config import settings


class Base(DeclarativeBase):
    pass


# ── ORM 模型 ──

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "teacher", "student", name="user_role"),
        default="student", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


class Topic(Base):
    """思政课程专题（任务书：完成 2 个专题案例库的构建）"""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


class Document(Base):
    """案例文档注册表（替代旧 SQLite registry，含案例元数据 + 专题 + 上传人留痕）"""
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")
    # 案例元数据
    case_title: Mapped[str] = mapped_column(String(200), default="")
    course: Mapped[str] = mapped_column(String(100), default="")
    case_type: Mapped[str] = mapped_column(String(50), default="")
    knowledge_points: Mapped[str] = mapped_column(String(500), default="")
    related_theory: Mapped[str] = mapped_column(String(500), default="")
    source_info: Mapped[str] = mapped_column(String(500), default="")  # 来源信息
    # 归属与留痕
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class QARecord(Base):
    """AI 生成内容登记：答疑（answer）与研习引导问题（guide_q）

    ai_content 不可变（原始输出），教师修改写入 final_content。
    citations 存 SourceRef 列表 JSON，支持前端引用回跳。
    """
    __tablename__ = "qa_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_type: Mapped[str] = mapped_column(
        Enum("answer", "guide_q", name="record_type"), nullable=False)
    question: Mapped[str] = mapped_column(Text, default="")     # 学生提问 / 所选案例标题
    ai_content: Mapped[str] = mapped_column(MediumText, nullable=False)
    final_content: Mapped[str | None] = mapped_column(MediumText)  # 教师修正稿
    citations: Mapped[list | None] = mapped_column(JSON)        # 引用来源列表
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    doc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # guide_q 关联案例
    status: Mapped[str] = mapped_column(
        Enum("pending", "corrected", "annotated", name="record_status"),
        default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


class ReviewLog(Base):
    """教师纠错留痕（追加只写：修改 edit / 批注 comment）"""
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("qa_records.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(
        Enum("edit", "comment", name="review_action"), nullable=False)
    content_before: Mapped[str] = mapped_column(Text, default="")  # 改动前快照
    content_after: Mapped[str] = mapped_column(Text, default="")   # 改动后内容/批注
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """通用操作审计：案例上传/修改/删除、角色变更等（追加只写）"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)


# ── 引擎与会话 ──

def _create_engine_and_session(url: str | None = None, create_db: bool = False):
    """create_db=True 时连接到 MySQL 服务器（不指定库），供 init_db 建库用"""
    if create_db:
        url = (f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
               f"@{settings.mysql_host}:{settings.mysql_port}/?charset=utf8mb4")
    engine = create_engine(url or settings.mysql_url, pool_pre_ping=True,
                           pool_recycle=3600)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


engine, SessionLocal = _create_engine_and_session()


def get_db():
    """FastAPI 依赖：请求级数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_audit(db, user_id: int | None, action: str,
              target_type: str = "", target_id: str = "", detail: str = "") -> None:
    """操作留痕（追加只写）。调用方负责 commit。"""
    db.add(AuditLog(user_id=user_id, action=action,
                    target_type=target_type, target_id=str(target_id),
                    detail=detail[:500]))


def dumps_citations(sources: list) -> str | None:
    """SourceRef 列表 → JSON 字符串（存 qa_records.citations）"""
    return json.dumps([s.model_dump() if hasattr(s, "model_dump") else s
                       for s in sources], ensure_ascii=False) if sources else None
