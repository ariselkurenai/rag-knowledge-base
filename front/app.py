"""Gradio 前端：知识库管理 + 多轮流式问答 + 引用溯源 + 参数面板

启动：python app.py web   或   python front/app.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr  # noqa: E402

from rag.config import settings  # noqa: E402
from rag.pipeline import get_pipeline  # noqa: E402
from rag.schemas import AskOptions  # noqa: E402


# ── 知识库管理 ──

def _doc_list_md():
    docs = get_pipeline().list_documents()
    if not docs:
        return "*（知识库为空，请先上传文档）*"
    lines = ["| 文档 | 页数 | 切块 | 已用字符 |", "|---|---|---|---|"]
    for d in docs:
        lines.append(f"| `{d.filename}` | {d.pages} | {d.chunks} | {d.chars} |")
    return "\n".join(lines)


def _doc_choices():
    return [(f"{d.filename}（{d.chunks} 块）", d.doc_id) for d in get_pipeline().list_documents()]


def ingest_files(files):
    if not files:
        return "❌ 请先选择文件", _doc_list_md(), gr.update(choices=_doc_choices())
    pipeline = get_pipeline()
    messages = []
    for f in files:
        with open(f.name, "rb") as fh:
            result = pipeline.ingest(fh.read(), os.path.basename(f.name))
        messages.append(("✅ " if result.success else "❌ ") + result.message)
    return "\n".join(messages), _doc_list_md(), gr.update(choices=_doc_choices())


def delete_doc(doc_id):
    if not doc_id:
        return "❌ 请先选择要删除的文档", _doc_list_md(), gr.update(choices=_doc_choices())
    ok = get_pipeline().delete_document(doc_id)
    msg = "🗑️ 已删除" if ok else "❌ 删除失败（文档不存在）"
    return msg, _doc_list_md(), gr.update(choices=_doc_choices(), value=None)


# ── 问答 ──

def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return ""
    lines = ["", "---", "📚 **引用来源**（⭐ = 答案中实际引用）"]
    for s in sources:
        mark = "⭐" if s.get("cited") else "　"
        lines.append(f"- {mark} [{s['index']}] {s['filename']} 第 {s['page']} 页"
                     f"（score {s.get('score', 0)}）")
    return "\n".join(lines)


def _format_latency(latency: dict) -> str:
    if not latency:
        return ""
    parts = []
    if latency.get("rewrite_ms"):
        parts.append(f"改写 {latency['rewrite_ms']:.0f}")
    parts.append(f"检索 {latency.get('retrieval_ms', 0):.0f}")
    if latency.get("first_token_ms"):
        parts.append(f"首字 {latency['first_token_ms']:.0f}")
    parts.append(f"总计 {latency.get('total_ms', 0):.0f}")
    return f"\n\n⏱ 延迟（ms）：{' · '.join(parts)}"


def chat(message, history, session_id, mode, use_rerank, top_k):
    options = AskOptions(
        retrieval_mode=mode,
        use_rerank=bool(use_rerank),
        top_k=int(top_k),
        rewrite_query=True,
    )
    collected: list[str] = []
    final_sources: list[dict] = []
    for event in get_pipeline().ask_stream(message, options, session_id):
        etype = event["type"]
        if etype == "delta":
            collected.append(event["text"])
            yield "".join(collected)
        elif etype == "sources":
            final_sources = event["sources"]
        elif etype == "done":
            yield (event["answer"]
                   + _format_sources(event.get("sources") or final_sources)
                   + _format_latency(event.get("latency_ms", {})))
        elif etype == "error":
            yield event["message"]
            return


def new_session():
    return get_pipeline().sessions.new_session()


# ── 界面 ──

def build_ui():
    pipeline = get_pipeline()

    with gr.Blocks(title="📚 RAG 知识库问答系统", theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"""
# 📚 基于 RAG 的私有知识库问答系统 v2.0
**LLM**: {settings.chat_model} | **Embedding**: {settings.embed_model} | **Rerank**: {settings.rerank_model}
| **检索**: 混合检索（向量 + BM25 + RRF 融合 + 重排序）

支持多文档入库（PDF / DOCX / TXT / MD）、多轮对话、流式输出与引用溯源。
        """)

        with gr.Row():
            # ---- 左栏：知识库管理 ----
            with gr.Column(scale=1):
                gr.Markdown("### 🗂️ 知识库管理")
                file_input = gr.File(
                    label="上传文档（可多选）",
                    file_types=[".pdf", ".docx", ".txt", ".md"],
                    type="filepath", file_count="multiple",
                )
                ingest_btn = gr.Button("📥 入库", variant="primary")
                ingest_status = gr.Textbox(label="入库状态", lines=3, interactive=False)
                doc_list = gr.Markdown(_doc_list_md())
                delete_dd = gr.Dropdown(label="选择要删除的文档", choices=_doc_choices())
                delete_btn = gr.Button("🗑️ 删除所选文档")

                gr.Markdown("### ⚙️ 检索参数")
                mode_radio = gr.Radio(
                    ["dense", "bm25", "hybrid"], value=settings.retrieval_mode,
                    label="检索模式", info="hybrid = 向量+BM25 融合")
                rerank_cb = gr.Checkbox(value=settings.use_rerank, label="启用重排序（gte-rerank）")
                topk_slider = gr.Slider(1, 10, value=settings.k_final, step=1,
                                        label="送入 LLM 的上下文条数 top-k")

            # ---- 右栏：问答 ----
            with gr.Column(scale=2):
                session_state = gr.State(pipeline.sessions.new_session())
                chat_ui = gr.ChatInterface(
                    chat,
                    additional_inputs=[session_state, mode_radio, rerank_cb, topk_slider],
                    title="💬 知识库问答",
                    description="基于已入库文档提问，答案附带 [n] 引用与来源页码",
                    examples=[["Flume 是什么？有什么特点？"],
                              ["Flume 的基础架构包含哪些组件？"],
                              ["它和 Kafka 有什么区别？"]],   # 第三例测试多轮指代改写
                )
                clear_mem_btn = gr.Button("🧹 清空对话记忆（重置多轮上下文）")

        ingest_btn.click(ingest_files, [file_input],
                         [ingest_status, doc_list, delete_dd])
        delete_btn.click(delete_doc, [delete_dd],
                         [ingest_status, doc_list, delete_dd])
        clear_mem_btn.click(new_session, [], [session_state])
    return demo


def main():
    build_ui().launch(server_name="127.0.0.1", server_port=7860, share=False)


if __name__ == "__main__":
    main()
