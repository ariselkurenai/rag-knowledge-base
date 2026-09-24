"""Embedding 客户端：DashScope OpenAI 兼容接口 + 磁盘缓存 + 批量重试

- 缓存以 sha1(model + text) 为键，重复入库同一文档不再重复计费；
- 批量大小 10（text-embedding-v4 单次上限），失败指数退避重试；
- FakeEmbeddings 用于离线单元测试，不发起网络请求。
"""

import hashlib
import json
import time
from pathlib import Path

from .config import settings

_BATCH_SIZE = 10
_MAX_RETRIES = 3


class DashScopeEmbeddings:
    """阿里百炼文本向量化（OpenAI 兼容协议）"""

    def __init__(self, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None, enable_cache: bool = True):
        from openai import OpenAI

        self.model = model or settings.embed_model
        self.enable_cache = enable_cache
        self._cache_dir = settings.cache_dir / "embeddings" / self.model
        if enable_cache:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = OpenAI(
            api_key=api_key or settings.dashscope_api_key,
            base_url=base_url or settings.dashscope_api_base,
        )

    # ── 缓存 ──

    def _cache_path(self, text: str) -> Path:
        digest = hashlib.sha1(f"{self.model}|{text}".encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _cache_get(self, text: str) -> list[float] | None:
        if not self.enable_cache:
            return None
        path = self._cache_path(text)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                path.unlink(missing_ok=True)
        return None

    def _cache_put(self, text: str, vector: list[float]) -> None:
        if self.enable_cache:
            self._cache_path(text).write_text(
                json.dumps(vector), encoding="utf-8")

    # ── 对外接口 ──

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float] | None] = [self._cache_get(t) for t in texts]
        miss_idx = [i for i, v in enumerate(vectors) if v is None]

        for batch_start in range(0, len(miss_idx), _BATCH_SIZE):
            batch = miss_idx[batch_start:batch_start + _BATCH_SIZE]
            resp = self._request_with_retry([texts[i] for i in batch])
            for i, item in zip(batch, resp.data):
                vectors[i] = item.embedding
                self._cache_put(texts[i], item.embedding)
        return vectors  # type: ignore[return-value]

    def embed_query(self, text: str) -> list[float]:
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        resp = self._request_with_retry([text])
        vector = resp.data[0].embedding
        self._cache_put(text, vector)
        return vector

    # ── 网络 ──

    def _request_with_retry(self, texts: list[str]):
        delay = 1.0
        for attempt in range(_MAX_RETRIES):
            try:
                return self.client.embeddings.create(model=self.model, input=texts)
            except Exception as e:
                if attempt == _MAX_RETRIES - 1:
                    raise RuntimeError(f"Embedding 请求失败（已重试 {_MAX_RETRIES} 次）：{e}") from e
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")


class FakeEmbeddings:
    """基于 token 哈希的词袋向量，仅用于离线测试。

    相同/相近的文本会得到相近的向量（共享词叠加在同一维度），
    使 dense 检索在无网络环境下仍表现合理。
    """

    def __init__(self, dim: int = 256, salt: str = ""):
        self.dim = dim
        self.salt = salt

    def _vector(self, text: str) -> list[float]:
        import hashlib
        import math
        import re

        vec = [0.0] * self.dim
        tokens = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text.lower())
        for tok in tokens:
            digest = hashlib.md5((self.salt + tok).encode("utf-8")).hexdigest()
            vec[int(digest, 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
