"""FastAPI 服务：高校思政课程案例研习系统（REST + SSE 流式）

启动：python -m rag.server   （默认 http://127.0.0.1:8000）
路由按业务域拆分在 rag/api/ 包：
  auth      注册/登录/当前用户          users     用户管理（管理员）
  topics    思政专题管理                documents 案例上传/元数据/原文/检索
  chat      研习答疑（SSE）/我的记录    review    教师审核纠错/引导问题生成
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .api import auth, chat, documents, review, topics, users
from .auth import get_current_user
from .database import QARecord, User, get_db
from .pipeline import get_pipeline

app = FastAPI(title="高校思政课程案例研习系统", version="3.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(topics.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(review.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/stats")
def stats(db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    data = get_pipeline().stats()
    data["pending_review"] = db.scalar(
        select(func.count(QARecord.id)).where(QARecord.status == "pending")) or 0
    data["qa_records"] = db.scalar(select(func.count(QARecord.id))) or 0
    return data


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
