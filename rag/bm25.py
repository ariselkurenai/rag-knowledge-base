"""BM25 稀疏检索（自实现 Okapi BM25）+ 中文分词 + 索引持久化

- 分词：优先 jieba（若安装），否则退化为「CJK 单字 + 英文单词 + 字符二元组」，
  保证纯标准库即可运行；
- 索引随 Chroma 全量切片重建，pickle 持久化到 data/ 目录；
- IDF 采用 Lucene 平滑公式，避免负权重。
"""

import logging
import math
import pickle
import re
from pathlib import Path
from typing import Optional

from .config import settings
from .loaders import _load_stopwords
from .schemas import Chunk

logger = logging.getLogger(__name__)

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

_EN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """中文分词：jieba → 停用词过滤；无 jieba 时退化为字符二元组"""
    if HAS_JIEBA:
        tokens = [t.strip() for t in jieba.lcut(text)]
    else:
        tokens = _EN_RE.findall(text.lower())
        chars = _CJK_RE.findall(text)
        # 单字 + 相邻二元组，兼顾召回率
        tokens += chars + [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    stop = _load_stopwords()
    return [t.lower() for t in tokens if t and t.lower() not in stop]


class BM25Store:
    """Okapi BM25 倒排索引（内存态，规模以万级切片为设计上限）"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks: dict[str, Chunk] = {}
        self.doc_tokens: dict[str, list[str]] = {}
        self.doc_len: dict[str, int] = {}
        self.inverted: dict[str, dict[str, int]] = {}  # term -> {chunk_id: tf}
        self._avgdl: float = 0.0
        self._idf: dict[str, float] = {}

    # ── 构建与持久化 ──

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = {c.chunk_id: c for c in chunks}
        self.doc_tokens = {}
        self.doc_len = {}
        self.inverted = {}
        for c in chunks:
            tokens = tokenize(c.content)
            self.doc_tokens[c.chunk_id] = tokens
            self.doc_len[c.chunk_id] = len(tokens)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            for term, freq in tf.items():
                self.inverted.setdefault(term, {})[c.chunk_id] = freq
        self._avgdl = (sum(self.doc_len.values()) / len(self.doc_len)) if self.doc_len else 0.0
        self._idf = {}
        logger.info("BM25 索引构建完成：%d 个切片，%d 个词项", len(chunks), len(self.inverted))

    def save(self, path: Optional[Path] = None) -> None:
        path = path or settings.bm25_index
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "chunks": self.chunks, "doc_tokens": self.doc_tokens,
                "doc_len": self.doc_len, "inverted": self.inverted,
                "avgdl": self._avgdl, "k1": self.k1, "b": self.b,
            }, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["BM25Store"]:
        path = path or settings.bm25_index
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            store = cls(k1=data["k1"], b=data["b"])
            store.chunks = data["chunks"]
            store.doc_tokens = data["doc_tokens"]
            store.doc_len = data["doc_len"]
            store.inverted = data["inverted"]
            store._avgdl = data["avgdl"]
            store._idf = {}
            return store
        except Exception as e:
            logger.warning("BM25 索引加载失败，将重建：%s", e)
            return None

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    # ── 检索 ──

    def _get_idf(self, term: str) -> float:
        if term not in self._idf:
            n = len(self.chunks)
            df = len(self.inverted.get(term, {}))
            # Lucene 平滑：恒正，避免长尾词出现负权重
            self._idf[term] = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
        return self._idf[term]

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        """返回 top-k 的 (chunk_id, bm25_score)，得分越高越相关"""
        if not self.chunks:
            return []
        scores: dict[str, float] = {}
        for term in set(tokenize(query)):
            postings = self.inverted.get(term)
            if not postings:
                continue
            idf = self._get_idf(term)
            for chunk_id, tf in postings.items():
                dl = self.doc_len[chunk_id]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self._avgdl, 1e-6))
                scores[chunk_id] = scores.get(chunk_id, 0.0) + idf * tf * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:k]
        return ranked
