"""重排序：DashScope gte-rerank（Cross-Encoder）→ DeepSeek LLM 打分（降级方案）

重排序器对 query 与每条候选文档做交叉编码打分，能修正向量检索
"语义相近但答非所问" 的错误。降级链：
1. DashScope gte-rerank：效果最好（需在百炼控制台开通该模型）；
2. LLM listwise 打分：一次调用为全部候选打 0-10 分，任何 OpenAI 兼容
   key 均可用，作为无 gte-rerank 权限时的兜底。
两级失败均不阻塞主流程（原样返回融合序）。
"""

import logging
from typing import Optional

import requests

from .config import settings
from .llm import ChatLLM, parse_json_reply
from .prompts import LLM_RERANK_PROMPT, build_llm_rerank_docs
from .schemas import ScoredChunk

logger = logging.getLogger(__name__)

_MAX_DOC_CHARS = 2000  # 单文档送审长度上限，避免超 token 限制


class DashScopeReranker:
    """gte-rerank 交叉编码重排序（DashScope 原生 HTTP 接口）"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or settings.rerank_model
        self.api_key = api_key or settings.dashscope_api_key
        self.endpoint = settings.rerank_api_base

    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: Optional[int] = None) -> list[ScoredChunk]:
        """对候选重排序。失败时抛异常，由上层 Reranker 决定降级路径。"""
        if not candidates:
            return []
        top_n = top_n or len(candidates)

        resp = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "input": {
                    "query": query,
                    "documents": [c.chunk.content[:_MAX_DOC_CHARS] for c in candidates],
                },
                "parameters": {"return_documents": False, "top_n": top_n},
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()["output"]["results"]

        reranked: list[ScoredChunk] = []
        for rank, item in enumerate(results):
            idx = item["index"]
            reranked.append(ScoredChunk(
                chunk=candidates[idx].chunk,
                score=float(item["relevance_score"]),
                rank=rank + 1, stage="rerank",
            ))
        return reranked


class LLMReranker:
    """LLM listwise 打分重排序：一次调用为全部候选打 0-10 相关性分"""

    def __init__(self, llm: Optional[ChatLLM] = None):
        self.llm = llm or ChatLLM()

    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: Optional[int] = None) -> list[ScoredChunk]:
        if not candidates:
            return []
        top_n = top_n or len(candidates)

        prompt = LLM_RERANK_PROMPT.format(
            query=query,
            documents=build_llm_rerank_docs([c.chunk.content for c in candidates]),
        )
        reply = self.llm.chat([{"role": "user", "content": prompt}],
                              temperature=0.0, json_mode=True)
        data = parse_json_reply(reply)
        scores = (data or {}).get("scores")
        if not isinstance(scores, list) or len(scores) != len(candidates):
            raise ValueError(f"LLM 重排序返回格式异常：{reply[:100]}")

        scored = [
            (float(s), i) for i, s in enumerate(scores)
            if isinstance(s, (int, float))
        ]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [
            ScoredChunk(chunk=candidates[i].chunk, score=score,
                        rank=rank + 1, stage="rerank-llm")
            for rank, (score, i) in enumerate(scored[:top_n])
        ]


class Reranker:
    """降级链外观：gte-rerank → LLM 打分 → 原序返回"""

    def __init__(self, dashscope: Optional[DashScopeReranker] = None,
                 llm_reranker: Optional[LLMReranker] = None):
        self.dashscope = dashscope or DashScopeReranker()
        self.llm_reranker = llm_reranker or LLMReranker()
        self._dashscope_disabled = False  # 首次 403/失败后本进程内不再重试

    def rerank(self, query: str, candidates: list[ScoredChunk],
               top_n: Optional[int] = None) -> list[ScoredChunk]:
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates[: (top_n or len(candidates))]

        if not self._dashscope_disabled:
            try:
                return self.dashscope.rerank(query, candidates, top_n)
            except Exception as e:
                logger.info("gte-rerank 不可用（%s），降级为 LLM 重排序", e)
                self._dashscope_disabled = True

        try:
            return self.llm_reranker.rerank(query, candidates, top_n)
        except Exception as e:
            logger.warning("LLM 重排序失败，保持 RRF 融合序：%s", e)
            return candidates[: (top_n or len(candidates))]
