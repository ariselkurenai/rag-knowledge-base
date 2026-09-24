"""混合检索编排：Dense + BM25 → RRF 融合 → Cross-Encoder 重排序

三种检索模式：
- dense ：纯向量语义检索
- bm25  ：纯关键词检索
- hybrid：双路召回 + Reciprocal Rank Fusion 融合 + 重排序（默认）

RRF 公式：score(d) = Σ_i 1 / (rrf_k + rank_i(d))，只用名次不用原始分数，
天然免疫两路检索分数量纲差异，是融合的标准做法。
"""

from .bm25 import BM25Store
from .rerank import DashScopeReranker
from .schemas import ScoredChunk
from .vectordb import VectorStore


def rrf_fuse(ranked_lists: list[list[str]], rrf_k: int = 60) -> dict[str, float]:
    """输入若干「按相关性降序的 chunk_id 列表」，输出融合得分（越高越相关）"""
    scores: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


class HybridRetriever:
    def __init__(self, vectorstore: VectorStore, bm25: BM25Store,
                 reranker: DashScopeReranker | None = None,
                 rrf_k: int = 60):
        self.vs = vectorstore
        self.bm25 = bm25
        self.reranker = reranker
        self.rrf_k = rrf_k

    # ── 单路检索 ──

    def _dense(self, query: str, k: int) -> list[ScoredChunk]:
        return self.vs.query(query, k)

    def _sparse(self, query: str, k: int) -> list[ScoredChunk]:
        results: list[ScoredChunk] = []
        for rank, (chunk_id, score) in enumerate(self.bm25.search(query, k), start=1):
            chunk = self.bm25.chunks.get(chunk_id)
            if chunk is not None:
                results.append(ScoredChunk(chunk=chunk, score=score, rank=rank, stage="bm25"))
        return results

    # ── 主入口 ──

    def retrieve(self, query: str, k: int, mode: str = "hybrid",
                 use_rerank: bool = True, rerank_candidates: int = 20,
                 where: dict | None = None) -> list[ScoredChunk]:
        """返回最终 top-k 上下文（按相关性降序）"""
        if mode == "dense":
            return self._dense(query, k)
        if mode == "bm25":
            return self._sparse(query, k)

        # hybrid：双路召回（重排序开启时加大召回深度）
        recall_k = rerank_candidates if use_rerank else max(k, 8)
        dense_hits = self._dense(query, recall_k)
        sparse_hits = self._sparse(query, recall_k)

        fused = rrf_fuse(
            [[c.chunk.chunk_id for c in dense_hits],
             [c.chunk.chunk_id for c in sparse_hits]],
            rrf_k=self.rrf_k,
        )
        by_id = {c.chunk.chunk_id: c for c in dense_hits + sparse_hits}
        ranked_ids = sorted(fused, key=lambda cid: -fused[cid])

        candidates = [
            ScoredChunk(chunk=by_id[cid].chunk, score=fused[cid],
                        rank=i + 1, stage="rrf")
            for i, cid in enumerate(ranked_ids)
        ]

        if use_rerank and self.reranker is not None:
            candidates = self.reranker.rerank(query, candidates, top_n=k)
        return candidates[:k]
