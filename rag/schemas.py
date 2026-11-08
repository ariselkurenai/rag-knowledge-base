"""数据模型：模块间传递的统一结构"""

from time import time
from typing import Optional

from pydantic import BaseModel, Field


# ── 文档与切片 ──

class CaseMeta(BaseModel):
    """案例元数据：用于案例库分类浏览与问答中的理论关联"""
    case_title: str = ""        # 案例名称，如「张桂梅与华坪女子高级中学」
    course: str = ""            # 所属思政课程，如「思想道德与法治」
    case_type: str = ""         # 案例类型：人物事迹 / 时政热点 / 法治案例 / 历史事件 / 实践成果
    knowledge_points: str = ""  # 关联知识点（顿号分隔），如「人生价值、理想信念」
    related_theory: str = ""    # 关联教材理论或原理

    def is_empty(self) -> bool:
        return not any((self.case_title, self.course, self.case_type,
                        self.knowledge_points, self.related_theory))

    @classmethod
    def from_front_matter(cls, meta: dict) -> Optional["CaseMeta"]:
        """从文档 front-matter 字典构造（title/case_title 均接受）"""
        case = cls(
            case_title=str(meta.get("case_title") or meta.get("title") or "").strip(),
            course=str(meta.get("course") or "").strip(),
            case_type=str(meta.get("case_type") or "").strip(),
            knowledge_points=str(meta.get("knowledge_points") or "").strip(),
            related_theory=str(meta.get("related_theory") or "").strip(),
        )
        return None if case.is_empty() else case


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
    # 案例元数据（Chroma metadata 仅存标量，知识点为顿号分隔单值）
    case_title: str = ""
    course: str = ""
    case_type: str = ""
    knowledge_points: str = ""


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
    case: Optional[CaseMeta] = None   # 案例元数据（无则文档未标注案例信息）
    source_info: str = ""             # 来源信息（教材/新闻出处等）
    topic_id: Optional[int] = None    # 所属专题（topics.id）
    uploader_id: Optional[int] = None # 上传人（users.id，操作留痕）


class IngestResult(BaseModel):
    success: bool
    message: str
    doc_id: Optional[str] = None
    pages: int = 0
    chunks: int = 0
    case_title: str = ""   # 入库识别出的案例名（便于回显与前端刷新）


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
    # 案例溯源信息
    case_title: str = ""
    course: str = ""
    case_type: str = ""
    knowledge_points: str = ""


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
