"""向量库封装：Chroma 持久化 + 文档级删除 + 模型指纹校验

- collection metadata 记录 embedding 模型名，换模型时自动重建集合，
  避免维度不一致导致的静默错误；
- 所有切片的元数据统一为 {doc_id, filename, page, chunk_index}。
"""

import logging
import uuid
from typing import Optional

import chromadb

from .config import settings
from .embeddings import DashScopeEmbeddings, FakeEmbeddings
from .schemas import Chunk, ScoredChunk

logger = logging.getLogger(__name__)

Embeddings = DashScopeEmbeddings | FakeEmbeddings


class VectorStore:
    def __init__(self, embeddings: Embeddings,
                 collection_name: Optional[str] = None,
                 persist_dir: Optional[str] = None):
        self.embeddings = embeddings
        self.collection_name = collection_name or settings.collection_name
        self._client = chromadb.PersistentClient(path=str(persist_dir or settings.persist_dir))
        self._collection = self._get_or_create_collection()

    # ── 集合管理 ──

    def _model_fingerprint(self) -> str:
        model = getattr(self.embeddings, "model", "fake")
        dim = getattr(self.embeddings, "dim", "api")
        return f"{model}:{dim}"

    def _get_or_create_collection(self):
        existing = self._client.list_collections()
        names = [c.name if hasattr(c, "name") else c for c in existing]

        if self.collection_name in names:
            col = self._client.get_collection(self.collection_name)
            recorded = (col.metadata or {}).get("embed_fingerprint")
            if recorded and recorded != self._model_fingerprint():
                logger.warning("Embedding 模型已变更（%s → %s），重建集合",
                               recorded, self._model_fingerprint())
                self._client.delete_collection(self.collection_name)
            else:
                return col
        return self._client.create_collection(
            name=self.collection_name,
            metadata={"embed_fingerprint": self._model_fingerprint()},
        )

    # ── 写入 ──

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        vectors = self.embeddings.embed_documents([c.content for c in chunks])
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.content for c in chunks],
            embeddings=vectors,
            metadatas=[{
                "doc_id": c.doc_id,
                "filename": c.filename,
                "page": c.page,
                "chunk_index": c.chunk_index,
            } for c in chunks],
        )
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        self._collection.delete(where={"doc_id": {"$eq": doc_id}})

    def clear(self) -> None:
        """清空集合（危险操作，仅供 CLI/测试使用）"""
        self._client.delete_collection(self.collection_name)
        self._collection = self._get_or_create_collection()

    # ── 查询 ──

    def query(self, query_text: str, k: int,
              where: Optional[dict] = None) -> list[ScoredChunk]:
        vector = self.embeddings.embed_query(query_text)
        res = self._collection.query(
            query_embeddings=[vector], n_results=min(k, self.count(where)),
            where=where, include=["documents", "metadatas", "distances"],
        )
        results: list[ScoredChunk] = []
        for i, chunk_id in enumerate(res["ids"][0]):
            meta = res["metadatas"][0][i]
            distance = res["distances"][0][i]
            results.append(ScoredChunk(
                chunk=Chunk(
                    chunk_id=chunk_id, doc_id=meta["doc_id"],
                    filename=meta["filename"], page=int(meta["page"]),
                    chunk_index=int(meta["chunk_index"]),
                    content=res["documents"][0][i],
                ),
                score=1.0 / (1.0 + float(distance)),
                rank=i + 1, stage="dense",
            ))
        return results

    def count(self, where: Optional[dict] = None) -> int:
        res = self._collection.count() if where is None else \
            self._collection.get(where=where, include=[])
        return res if isinstance(res, int) else len(res["ids"])

    def get_all_chunks(self) -> list[Chunk]:
        """全量读取切片（BM25 重建索引 / 评测集生成用）"""
        res = self._collection.get(include=["documents", "metadatas"])
        chunks = []
        for chunk_id, content, meta in zip(res["ids"], res["documents"], res["metadatas"]):
            chunks.append(Chunk(
                chunk_id=chunk_id, doc_id=meta["doc_id"],
                filename=meta["filename"], page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]), content=content,
            ))
        return chunks


def new_doc_id() -> str:
    return uuid.uuid4().hex[:12]
