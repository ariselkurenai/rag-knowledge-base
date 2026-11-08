"""Gradio 前端：思政案例库管理 + 案例浏览 + 多轮流式问答 + 引用溯源

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

ALL_COURSES = "全部课程"


# ── 案例库管理 ──

def _doc_list_md():
    docs = get_pipeline().list_documents()
    if not docs:
        return "*（案例库为空，请先上传案例文档）*"
    lines = ["| 案例 | 课程 | 类型 | 知识点 | 切块 |", "|---|---|---|---|---|"]
    for d in docs:
        if d.case:
            lines.append(f"| 《{d.case.case_title}》 | {d.case.course} | "
                         f"{d.case.case_type} | {d.case.knowledge_points} | {d.chunks} |")
        else:
            lines.append(f"| `{d.filename}` | - | - | - | {d.chunks} |")
    return "\n".join(lines)


def _course_choices():
    courses = sorted({d.case.course for d in get_pipeline().list_documents()
                      if d.case and d.case.course})
    return [ALL_COURSES] + courses


def _case_cards(course=ALL_COURSES):
    """按课程筛选渲染案例卡片（用于案例库分类浏览）"""
    docs = get_pipeline().list_documents()
    cards = []
    for d in docs:
        if not d.case:
            continue
        if course != ALL_COURSES and d.case.course != course:
            continue
        c = d.case
        cards.append(
            f"**《{c.case_title}》**（{d.chunks} 块）\n\n"
            f"- 课程：{c.course} ｜ 类型：{c.case_type}\n"
            f"- 知识点：{c.knowledge_points}\n"
            f"- 关联理论：{c.related_theory}"
        )
    if not cards:
        return ("*（暂无带元数据的案例。请上传含 front-matter 的 Markdown 案例文档，"
                "或上传 PDF/DOCX 由系统自动抽取案例元数据）*")
    return "\n\n---\n\n".join(cards)


def _doc_choices():
    return [(f"{d.case.case_title if d.case else d.filename}（{d.chunks} 块）",
             d.doc_id) for d in get_pipeline().list_documents()]


def ingest_files(files):
    if not files:
        return ("❌ 请先选择文件", _doc_list_md(), gr.update(choices=_doc_choices()),
                _course_choices(), _case_cards())
    pipeline = get_pipeline()
    messages = []
    for f in files:
        with open(f.name, "rb") as fh:
            result = pipeline.ingest(fh.read(), os.path.basename(f.name))
        messages.append(("✅ " if result.success else "❌ ") + result.message)
    return ("\n".join(messages), _doc_list_md(), gr.update(choices=_doc_choices()),
            gr.update(choices=_course_choices(), value=ALL_COURSES), _case_cards())


def delete_doc(doc_id):
    if not doc_id:
        return ("❌ 请先选择要删除的案例", _doc_list_md(), gr.update(choices=_doc_choices()),
                _course_choices(), _case_cards())
    ok = get_pipeline().delete_document(doc_id)
    msg = "🗑️ 已删除" if ok else "❌ 删除失败（案例不存在）"
    return (msg, _doc_list_md(), gr.update(choices=_doc_choices(), value=None),
            gr.update(choices=_course_choices(), value=ALL_COURSES), _case_cards())


# ── 问答 ──

def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return ""
    lines = ["", "---", "📚 **引用来源**（⭐ = 答案中实际引用）"]
    for s in sources:
        mark = "⭐" if s.get("cited") else "　"
        name = f"《{s['case_title']}》" if s.get("case_title") else s["filename"]
        course = f"（{s['course']}）" if s.get("course") else ""
        kp = f" ｜ 知识点：{s['knowledge_points']}" if s.get("knowledge_points") else ""
        lines.append(f"- {mark} [{s['index']}] {name}{course} 第 {s['page']} 页{kp}"
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

    with gr.Blocks(title="🎓 高校思政课程案例研习系统") as demo:
        gr.Markdown(f"""
# 🎓 高校思政课程案例研习系统
**LLM**: {settings.chat_model} | **Embedding**: {settings.embed_model} | **Rerank**: {settings.rerank_model}
| **检索**: 混合检索（向量 + BM25 + RRF 融合 + 重排序）

基于检索增强生成（RAG）技术，支持思政案例入库与元数据自动抽取、按课程分类浏览、
案例问答与理论关联，答案附带 [n] 引用并溯源到案例、页码与知识点。
        """)

        with gr.Row():
            # ---- 左栏：案例库管理 ----
            with gr.Column(scale=1):
                gr.Markdown("### 🗂️ 案例库管理")
                file_input = gr.File(
                    label="上传案例文档（可多选；MD 支持 front-matter，PDF/DOCX 自动抽取元数据）",
                    file_types=[".pdf", ".docx", ".txt", ".md"],
                    type="filepath", file_count="multiple",
                )
                ingest_btn = gr.Button("📥 入库", variant="primary")
                ingest_status = gr.Textbox(label="入库状态", lines=3, interactive=False)
                doc_list = gr.Markdown(_doc_list_md())
                delete_dd = gr.Dropdown(label="选择要删除的案例", choices=_doc_choices())
                delete_btn = gr.Button("🗑️ 删除所选案例")

                gr.Markdown("### 📚 案例库浏览")
                course_dd = gr.Dropdown(label="按课程筛选", choices=_course_choices(),
                                        value=ALL_COURSES)
                case_cards = gr.Markdown(_case_cards())

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
                    title="💬 案例研习问答",
                    description="围绕思政案例提问，答案结合案例事实与理论观点，"
                                "并附 [n] 引用与来源（案例名/页码/知识点）",
                    examples=[["张桂梅的事迹体现了怎样的人生价值追求？"],
                              ["民法典第184条为什么被称为'好人条款'？"],
                              ["塞罕坝的蜕变如何体现量变质变规律？"],
                              ["精准扶贫理念是何时何地首次提出的？"],
                              ["嫦娥探月工程'绕、落、回'分别由哪次任务实现？"]],
                )
                clear_mem_btn = gr.Button("🧹 清空对话记忆（重置多轮上下文）")

        ingest_btn.click(ingest_files, [file_input],
                         [ingest_status, doc_list, delete_dd, course_dd, case_cards])
        delete_btn.click(delete_doc, [delete_dd],
                         [ingest_status, doc_list, delete_dd, course_dd, case_cards])
        course_dd.change(_case_cards, [course_dd], [case_cards])
        clear_mem_btn.click(new_session, [], [session_state])
    return demo


def main():
    build_ui().launch(server_name="127.0.0.1", server_port=7860, share=False,
                      theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
