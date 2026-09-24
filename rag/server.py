"""FastAPI 服务：REST + SSE 流式

启动：python -m rag.server   （默认 http://127.0.0.1:8000）
接口：
  GET  /api/health                     健康检查
  GET  /api/stats                      知识库统计
  GET  /api/documents                  文档列表
  POST /api/documents                  上传文档（multipart）
  DELETE /api/documents/{doc_id}       删除文档
  POST /api/sessions                   新建会话（多轮记忆）
  POST /api/chat                       问答（JSON；stream=true 返回 SSE）
"""

import json
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings
from .pipeline import get_pipeline
from .schemas import AskOptions

app = FastAPI(title="RAG 知识库问答系统", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    stream: bool = False
    # 可选参数覆盖
    retrieval_mode: Optional[str] = None
    use_rerank: Optional[bool] = None
    top_k: Optional[int] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/stats")
def stats():
    return get_pipeline().stats()


@app.get("/api/documents")
def list_documents():
    return [d.model_dump() for d in get_pipeline().list_documents()]


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    data = await file.read()
    result = get_pipeline().ingest(data, file.filename)
    if not result.success:
        raise HTTPException(422, result.message)
    return result.model_dump()


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    if not get_pipeline().delete_document(doc_id):
        raise HTTPException(404, f"文档不存在：{doc_id}")
    return {"success": True, "message": f"文档 {doc_id} 已删除"}


@app.post("/api/sessions")
def new_session():
    return {"session_id": get_pipeline().sessions.new_session()}


@app.post("/api/chat")
def chat(req: ChatRequest):
    pipeline = get_pipeline()
    options = AskOptions(
        retrieval_mode=req.retrieval_mode,
        use_rerank=req.use_rerank,
        top_k=req.top_k,
    )

    if not req.stream:
        result = pipeline.ask(req.question, options, req.session_id)
        return result.model_dump()

    def sse():
        for event in pipeline.ask_stream(req.question, options, req.session_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
