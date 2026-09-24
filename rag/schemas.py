"""数据模型：模块间传递的统一结构"""

from time import time
from typing import Optional

from pydantic import BaseModel, Field


# ── 文档与切片 ──

class PageContent(BaseModel):
    """单页原始文本"""
    page: int          # 1 起
    text: str


class Chunk(BaseModel):
    """切片：检索与引用的最小单位"""
    chunk_id: str      # {doc_id}:{chunk_index}
    doc_id: str
    filename: str
    page: int
    chunk_index: int
    content: str


class ScoredChunk(BaseModel):
    """检索结果中的切片（带得分与名次）"""
    chunk: Chunk
    score: float = 0.0
    rank: int = 0
    stage: str = ""    # 来源阶段：dense / bm25 / rrf / rerank


class DocInfo(BaseModel):
    """文档注册表记录"""
    doc_id: str
    filename: str
    pages: int
    chunks: int
    chars: int
    added_at: float = Field(default_factory=time)
    status: str = "active"


class IngestResult(BaseModel):
    success: bool
    message: str
    doc_id: Optional[str] = None
    pages: int = 0
    chunks: int = 0


# ── 问答 ──

class AskOptions(BaseModel):
    """单次问答的可调参数（用于前端/API 覆盖默认配置）"""
    retrieval_mode: Optional[str] = None   # dense | bm25 | hybrid
    use_rerank: Optional[bool] = None
    top_k: Optional[int] = None
    rewrite_query: Optional[bool] = None


class SourceRef(BaseModel):
    """答案引用来源"""
    index: int         # 上下文中的编号 [n]
    filename: str
    page: int
    chunk_id: str
    score: float = 0.0
    cited: bool = False  # 答案正文中是否出现 [n]


class AskResponse(BaseModel):
    success: bool
    answer: str = ""
    sources: list[SourceRef] = []
    rewritten_query: str = ""
    latency_ms: dict[str, float] = Field(default_factory=dict)


# ── 评估 ──

class EvalQuestion(BaseModel):
    """评测集中的一道题"""
    question: str
    answer: str                       # 金标答案
    expected_chunk_id: str
    expected_filename: str
    expected_page: int


class RetrievalMetrics(BaseModel):
    mode: str
    n: int
    hit_at_k: float                    # Top-k 命中率
    mrr: float                         # 平均倒数排名
    page_recall_at_k: float            # 页面级召回
    avg_latency_ms: float = 0.0


class GenerationMetrics(BaseModel):
    n: int
    faithfulness: float                # 忠实度 1-5（答案是否由上下文支撑）
    answer_relevance: float            # 相关性 1-5（是否回答了问题）
    avg_latency_ms: float = 0.0
