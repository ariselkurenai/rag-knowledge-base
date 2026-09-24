"""项目入口（命令行）

常用命令：
  python app.py ingest docs/test.pdf     # 入库文档
  python app.py ask "Flume 是什么？"     # 单次问答
  python app.py stats                    # 知识库统计
  python app.py serve                    # 启动 FastAPI 服务(8000)
  python app.py web                      # 启动 Gradio 网页界面(7860)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _cmd_ingest(args):
    from scripts.ingest import main as ingest_main
    sys.argv = ["ingest"] + args
    ingest_main()


def _cmd_ask(args):
    if not args:
        print("用法：python app.py ask \"你的问题\"")
        return
    from rag.pipeline import get_pipeline

    result = get_pipeline().ask(" ".join(args))
    print(result.answer)
    for s in result.sources:
        mark = "⭐" if s.cited else "  "
        print(f" {mark} [{s.index}] {s.filename} 第 {s.page} 页 (score={s.score})")


def _cmd_stats(_args):
    from rag.pipeline import get_pipeline
    from rag.config import settings
    for k, v in get_pipeline().stats().items():
        print(f"{k:>14}：{v}")
    print(f"{'retrieval':>14}：{settings.retrieval_mode} + rerank({settings.use_rerank})")


def _cmd_serve(_args):
    from rag.server import main
    main()


def _cmd_web(_args):
    from front.app import main
    main()


# ── 旧版兼容接口（v1 遗留，新代码请使用 rag.pipeline）──

def build_knowledge_base(pdf_bytes: bytes, filename: str = "upload.pdf") -> dict:
    from rag.pipeline import get_pipeline
    r = get_pipeline().ingest(pdf_bytes, filename)
    return {"success": r.success, "message": r.message, "chunk_count": r.chunks}


def ask(question: str) -> dict:
    from rag.pipeline import get_pipeline
    r = get_pipeline().ask(question)
    return {"success": r.success, "answer": r.answer,
            "sources": [s.model_dump() for s in r.sources]}


COMMANDS = {
    "ingest": _cmd_ingest,
    "ask": _cmd_ask,
    "stats": _cmd_stats,
    "serve": _cmd_serve,
    "web": _cmd_web,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
