"""初始化 MySQL 数据库：建库 → 建表 → 种子数据（管理员/教师账号 + 2 个专题）

用法：python scripts/init_db.py
可重复运行（幂等）：库表已存在则跳过，种子账号/专题缺失才补。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymysql
from sqlalchemy import select, text

from rag.config import settings
from rag.database import Base, SessionLocal, Topic, User, _create_engine_and_session


def create_database() -> None:
    """连接 MySQL 服务器建库（utf8mb4 支持中文与 emoji）"""
    conn = pymysql.connect(host=settings.mysql_host, port=settings.mysql_port,
                           user=settings.mysql_user,
                           password=settings.mysql_password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS {settings.mysql_database} "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        print(f"[1/3] 数据库 `{settings.mysql_database}` 已就绪")
    finally:
        conn.close()


def create_tables() -> None:
    engine, _ = _create_engine_and_session()
    Base.metadata.create_all(engine)
    engine.dispose()
    print("[2/3] 数据表已就绪：users / topics / documents / qa_records / "
          "review_logs / audit_logs")


def seed_data() -> None:
    from rag.auth import hash_password

    db = SessionLocal()
    try:
        # 种子账号（幂等：不存在才建）
        seeds = [
            ("admin", "123456", "admin", "系统管理员"),
            ("teacher", "123456", "teacher", "演示教师"),
        ]
        for username, pwd, role, _desc in seeds:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(User(username=username,
                            password_hash=hash_password(pwd), role=role))
        # 种子专题（任务书：2 个思政课程专题案例库）
        topics = [
            ("理想信念与人生价值",
             "聚焦理想信念、人生价值与道德实践主题，涵盖张桂梅事迹、"
             "民法典好人条款、十八洞村精准扶贫等案例"),
            ("科技强国与绿色发展",
             "聚焦科技自立自强与生态文明建设主题，涵盖嫦娥探月、"
             "塞罕坝林场、高质量发展新格局等案例"),
        ]
        for name, desc in topics:
            if not db.scalar(select(Topic).where(Topic.name == name)):
                db.add(Topic(name=name, description=desc))
        db.commit()
        print("[3/3] 种子数据已就绪")
        print("  演示账号：admin / 123456（管理员），teacher / 123456（教师）")
        print("  专题：理想信念与人生价值 / 科技强国与绿色发展")
        print("  学生账号请在前端注册页自助注册")
    finally:
        db.close()


if __name__ == "__main__":
    create_database()
    create_tables()
    seed_data()
    print("初始化完成。")
