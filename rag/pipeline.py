"""RAG 管线编排：案例入库 → 混合检索 → 生成 → 引用溯源

完整链路：
  入库：加载(PDF/DOCX/TXT/MD) → 中文归一化 → 案例元数据(front-matter / LLM 抽取兜底)
        → 递归切片 → Embedding(带缓存) → Chroma 持久化 → BM25 重建 → SQLite 注册
  问答：多轮改写 → 双路召回(Dense+BM25) → RRF 融合 → Rerank
        → 流式生成(带[n]引用, 资料头含案例元数据) → 引用解析 → 会话记忆更新

所有阶段记录耗时（latency_ms），供性能分析与论文实验使用。
"""

import logging
import time
from typing import Generator, Optional

from .bm25 import BM25Store
from .chunking import chunk_stats, parse_citations, split_pages
from .config import settings
from .embeddings import DashScopeEmbeddings
from .llm import ChatLLM, parse_json_reply
from .loaders import load_document_with_meta
from .memory import SessionStore
from .prompts import (CASE_META_EXTRACT_PROMPT, GUIDE_QUESTION_PROMPT,
                      RAG_SYSTEM_PROMPT, build_case_context,
                      build_condense_prompt, build_rag_user_prompt)
from .registry import DocumentRegistry
from .rerank import Reranker
from .retrieval import HybridRetriever
from .schemas import (AskOptions, AskResponse, CaseMeta, DocInfo,
                      IngestResult, ScoredChunk, SourceRef)
from .vectordb import VectorStore, new_doc_id

logger = logging.getLogger(__name__)


class RagPipeline:
    def __init__(self, embeddings=None, llm: Optional[ChatLLM] = None):
        self.embeddings = embeddings or DashScopeEmbeddings()
        self.llm = llm or ChatLLM()
        self.vs = VectorStore(self.embeddings)
        self.bm25 = BM25Store.load() or BM25Store()
        self.reranker = Reranker()
        self.retriever = HybridRetriever(self.vs, self.bm25, self.reranker,
                                         rrf_k=settings.rrf_k)
        self.registry = DocumentRegistry()
        self.sessions = SessionStore()
        self._sync_bm25_if_stale()

    # ── 索引一致性 ──

    def _sync_bm25_if_stale(self) -> None:
        """BM25 与 Chroma 切片数不一致时全量重建（单副本真源：Chroma）"""
        chroma_count = self.vs.count()
        if self.bm25.chunk_count != chroma_count:
            logger.info("BM25 索引过期（%d/%d），重建中…", self.bm25.chunk_count, chroma_count)
            self.bm25.build(self.vs.get_all_chunks())
            self.bm25.save()

    def rebuild_bm25(self) -> None:
        self.bm25.build(self.vs.get_all_chunks())
        self.bm25.save()

    # ══════════ 文档管理 ══════════

    def ingest(self, data: bytes, filename: str, *,
               source_info: str = "", topic_id: int | None = None,
               uploader_id: int | None = None) -> IngestResult:
        t0 = time.perf_counter()
        try:
            pages, front_meta = load_document_with_meta(data, filename)
            doc_id = new_doc_id()

            # 同名文档重新入库：先删除旧版本
            old = self.registry.find_active_by_filename(filename)
            if old:
                self.delete_document(old.doc_id)
                doc_id = old.doc_id  # 复用 doc_id，引用不漂移

            # 案例元数据：front-matter 优先，缺失时 LLM 自动抽取兜底
            case = (CaseMeta.from_front_matter(front_meta)
                    or self._extract_case_meta(pages))

            chunks = split_pages(pages, doc_id, filename)
            if not chunks:
                return IngestResult(success=False, message="切片结果为空", doc_id=doc_id)
            if case:
                for c in chunks:
                    c.case_title = case.case_title
                    c.course = case.course
                    c.case_type = case.case_type
                    c.knowledge_points = case.knowledge_points
            self.vs.add_chunks(chunks)
            self.rebuild_bm25()

            info = DocInfo(
                doc_id=doc_id, filename=filename,
                pages=len(pages), chunks=len(chunks),
                chars=sum(len(c.content) for c in chunks),
                case=case,
                source_info=str(front_meta.get("source") or source_info or ""),
                topic_id=topic_id, uploader_id=uploader_id,
            )
            self.registry.add(info)

            stats = chunk_stats(chunks)
            elapsed = (time.perf_counter() - t0) * 1000
            case_note = f"，案例《{case.case_title}》（{case.course}）" if case else ""
            return IngestResult(
                success=True,
                message=(f"入库成功：{len(pages)} 页 → {stats['chunks']} 块"
                         f"（平均 {stats['avg_len']} 字），耗时 {elapsed:.0f} ms{case_note}"),
                doc_id=doc_id, pages=len(pages), chunks=len(chunks),
                case_title=case.case_title if case else "",
            )
        except Exception as e:
            logger.exception("入库失败：%s", filename)
            return IngestResult(success=False, message=f"入库失败：{e}")

    def _extract_case_meta(self, pages) -> Optional[CaseMeta]:
        """LLM 自动抽取案例元数据（PDF/DOCX 等无 front-matter 文档的兜底）。

        抽取失败留空、不阻塞入库——与重排序降级链保持同一可用性哲学。
        """
        content = "\n".join(p.text for p in pages).strip()
        if not content:
            return None
        try:
            reply = self.llm.chat(
                [{"role": "user",
                  "content": CASE_META_EXTRACT_PROMPT.format(content=content[:4000])}],
                temperature=0.0, json_mode=True, max_tokens=500,
            )
            data = parse_json_reply(reply)
            if data:
                case = CaseMeta(
                    case_title=str(data.get("case_title", "")).strip(),
                    course=str(data.get("course", "")).strip(),
                    case_type=str(data.get("case_type", "")).strip(),
                    knowledge_points=str(data.get("knowledge_points", "")).strip(),
                    related_theory=str(data.get("related_theory", "")).strip(),
                )
                if not case.is_empty():
                    return case
        except Exception as e:
            logger.warning("案例元数据抽取失败（不影响入库）：%s", e)
        return None

    def generate_guide_questions(self, doc_id: str, n: int = 5) -> dict:
        """研习引导问题生成（任务书模块5）。

        取该案例全部切片构造上下文 → LLM 生成 n 道课堂引导问题。
        返回 {"case_title", "questions": [{question, ref, chunk}], "chunks"}——
        ref/chunk 用于前端回跳到关联原文片段。
        """
        info = self.registry.get(doc_id)
        if not info:
            return {"success": False, "message": f"案例不存在：{doc_id}"}
        chunks = [c for c in self.vs.get_all_chunks() if c.doc_id == doc_id]
        if not chunks:
            return {"success": False, "message": "该案例没有可用的文本切片"}

        content = "\n\n".join(
            f"【{i}】{c.content}" for i, c in enumerate(chunks, start=1))
        reply = self.llm.chat(
            [{"role": "user",
              "content": GUIDE_QUESTION_PROMPT.format(content=content[:6000], n=n)}],
            temperature=0.3, json_mode=True, max_tokens=1500,
        )
        data = parse_json_reply(reply) or {}
        questions = []
        for q in (data.get("questions") or [])[:n]:
            if not isinstance(q, dict) or not q.get("question"):
                continue
            try:
                ref = int(q.get("ref", 1))
            except (TypeError, ValueError):
                ref = 1
            ref = min(max(ref, 1), len(chunks))
            chunk = chunks[ref - 1]
            questions.append({
                "question": str(q["question"]).strip(), "ref": ref,
                "chunk": {"chunk_id": chunk.chunk_id, "page": chunk.page,
                          "content": chunk.content,
                          "case_title": chunk.case_title or info.case.case_title if info.case else ""},
            })
        if not questions:
            return {"success": False, "message": "引导问题生成失败，请稍后重试"}
        return {"success": True, "doc_id": doc_id,
                "case_title": info.case.case_title if info.case else info.filename,
                "questions": questions}

    def delete_document(self, doc_id: str) -> bool:
        info = self.registry.get(doc_id)
        if not info:
            return False
        self.vs.delete_document(doc_id)
        self.rebuild_bm25()
        self.registry.mark_deleted(doc_id)
        return True

    def list_documents(self) -> list[DocInfo]:
        return self.registry.list_active()

    def retrieve(self, query: str, k: int = 4,
                 mode: Optional[str] = None,
                 use_rerank: Optional[bool] = None,
                 topic_id: Optional[int] = None) -> list[ScoredChunk]:
        """公开检索入口（供 /api/cases/search 使用，可限定专题范围）"""
        opts = self._resolve_options(AskOptions(
            retrieval_mode=mode, use_rerank=use_rerank, top_k=k,
            topic_id=topic_id))
        hits, _ = self._retrieve(query, opts)
        return hits

    def stats(self) -> dict:
        chunks = self.vs.get_all_chunks()
        docs = self.registry.list_active()
        courses = sorted({d.case.course for d in docs if d.case and d.case.course})
        return {
            "documents": len(docs),
            "cases": sum(1 for d in docs if d.case),
            "courses": len(courses),
            "chunks": len(chunks),
            "bm25_terms": len(self.bm25.inverted),
            "sessions": self.sessions.session_count,
            "embed_model": settings.embed_model,
            "chat_model": settings.chat_model,
        }

    # ══════════ 问答 ══════════

    def _resolve_options(self, opts: Optional[AskOptions]) -> AskOptions:
        opts = opts or AskOptions()
        return AskOptions(
            retrieval_mode=opts.retrieval_mode or settings.retrieval_mode,
            use_rerank=settings.use_rerank if opts.use_rerank is None else opts.use_rerank,
            top_k=opts.top_k or settings.k_final,
            rewrite_query=(settings.enable_query_rewrite if opts.rewrite_query is None
                           else opts.rewrite_query),
            topic_id=opts.topic_id,
        )

    def _rewrite(self, question: str, history: list[dict]) -> tuple[str, float]:
        if not history:
            return question, 0.0
        t0 = time.perf_counter()
        try:
            rewritten = self.llm.chat(build_condense_prompt(history, question),
                                      temperature=0.0, max_tokens=256).strip()
            rewritten = rewritten.strip('"“” ')
            if rewritten and len(rewritten) < len(question) * 6:
                return rewritten or question, (time.perf_counter() - t0) * 1000
        except Exception as e:
            logger.warning("查询改写失败，使用原始问题：%s", e)
        return question, (time.perf_counter() - t0) * 1000

    def _retrieve(self, query: str, opts: AskOptions) -> tuple[list[ScoredChunk], float]:
        t0 = time.perf_counter()
        allowed = None
        if opts.topic_id is not None:
            # 专题过滤：白名单内 doc_id 才参与检索（空专题 → 无命中）
            allowed = {d.doc_id for d in self.registry.list_by_topic(opts.topic_id)}
        hits = self.retriever.retrieve(
            query, k=opts.top_k, mode=opts.retrieval_mode,
            use_rerank=opts.use_rerank, rerank_candidates=settings.rerank_candidates,
            allowed_doc_ids=allowed,
        )
        return hits, (time.perf_counter() - t0) * 1000

    @staticmethod
    def _build_sources(hits: list[ScoredChunk], cited_ids: set[int]) -> list[SourceRef]:
        sources = []
        for i, hit in enumerate(hits, start=1):
            c = hit.chunk
            sources.append(SourceRef(
                index=i, doc_id=c.doc_id, filename=c.filename, page=c.page,
                chunk_id=c.chunk_id, chunk_index=c.chunk_index,
                score=round(hit.score, 4),
                cited=i in cited_ids,
                case_title=c.case_title, course=c.course,
                case_type=c.case_type, knowledge_points=c.knowledge_points,
            ))
        return sources

    @staticmethod
    def _flat_hits(hits: list[ScoredChunk]) -> list[dict]:
        """检索命中平铺为前端可直接消费的字典（与 SourceRef 字段对齐）"""
        return [{
            "chunk_id": h.chunk.chunk_id, "doc_id": h.chunk.doc_id,
            "chunk_index": h.chunk.chunk_index,
            "filename": h.chunk.filename, "page": h.chunk.page,
            "content": h.chunk.content, "score": round(h.score, 4),
            "stage": h.stage, "case_title": h.chunk.case_title,
            "course": h.chunk.course, "case_type": h.chunk.case_type,
            "knowledge_points": h.chunk.knowledge_points,
        } for h in hits]

    def ask(self, question: str, options: Optional[AskOptions] = None,
            session_id: Optional[str] = None) -> AskResponse:
        """同步问答（内部聚合流式结果）"""
        parts: list[str] = []
        final: dict = {}
        for event in self.ask_stream(question, options, session_id):
            if event["type"] == "delta":
                parts.append(event["text"])
            elif event["type"] == "done":
                final = event
        return AskResponse(
            success=True, answer="".join(parts),
            sources=final.get("sources", []),
            rewritten_query=final.get("rewritten_query", ""),
            latency_ms=final.get("latency_ms", {}),
        )

    def ask_stream(self, question: str, options: Optional[AskOptions] = None,
                   session_id: Optional[str] = None) -> Generator[dict, None, None]:
        """流式问答。事件流：
        {"type": "sources", "sources": [...]}          # 检索完成（含改写后问题）
        {"type": "delta", "text": "..."}               # 生成增量
        {"type": "done", "answer", "sources", "latency_ms"}
        {"type": "error", "message": "..."}
        """
        t_total = time.perf_counter()
        opts = self._resolve_options(options)

        if self.vs.count() == 0:
            yield {"type": "error", "message": "⚠️ 案例库为空，请先上传案例文档"}
            return

        try:
            # ① 多轮改写
            history = self.sessions.get_history(session_id)
            query, rewrite_ms = (self._rewrite(question, history)
                                 if opts.rewrite_query else (question, 0.0))

            # ② 混合检索 + 重排序
            hits, retrieval_ms = self._retrieve(query, opts)
            if not hits:
                yield {"type": "done", "answer": "案例库中未检索到相关内容。",
                       "sources": [], "rewritten_query": query,
                       "latency_ms": {"retrieval_ms": retrieval_ms}}
                return
            yield {"type": "sources", "rewritten_query": query,
                   "sources": self._flat_hits(hits)}

            # ③ 流式生成（资料头携带案例元数据，引导理论与案例关联）
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": build_rag_user_prompt(
                    question, build_case_context(hits))},
            ]
            answer_parts: list[str] = []
            t_first: Optional[float] = None
            t_llm0 = time.perf_counter()
            for delta in self.llm.stream(messages):
                if t_first is None:
                    t_first = time.perf_counter()
                answer_parts.append(delta)
                yield {"type": "delta", "text": delta}
            llm_ms = (time.perf_counter() - t_llm0) * 1000
            answer = "".join(answer_parts)

            # ④ 引用解析 + 会话记忆
            sources = self._build_sources(hits, parse_citations(answer))
            self.sessions.add_turn(session_id, question, answer)

            latency = {
                "rewrite_ms": round(rewrite_ms, 1),
                "retrieval_ms": round(retrieval_ms, 1),
                "first_token_ms": round((t_first - t_total) * 1000, 1) if t_first else None,
                "llm_ms": round(llm_ms, 1),
                "total_ms": round((time.perf_counter() - t_total) * 1000, 1),
            }
            yield {"type": "done", "answer": answer,
                   "sources": [s.model_dump() for s in sources],
                   "rewritten_query": query, "latency_ms": latency}
        except Exception as e:
            logger.exception("问答失败")
            yield {"type": "error", "message": f"❌ 问答出错：{e}"}


# ── 进程级单例（FastAPI / Gradio 共用）──

_pipeline: Optional[RagPipeline] = None


def get_pipeline() -> RagPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RagPipeline()
    return _pipeline
