"""离线单元测试：BM25 / RRF / 混合检索（FakeEmbeddings + 临时 Chroma，无网络）"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.bm25 import BM25Store, tokenize  # noqa: E402
from rag.embeddings import FakeEmbeddings  # noqa: E402
from rag.retrieval import HybridRetriever, rrf_fuse  # noqa: E402
from rag.schemas import Chunk  # noqa: E402
from rag.vectordb import VectorStore  # noqa: E402

CORPUS = [
    ("Flume 是 Cloudera 提供的高可用分布式海量日志采集系统", "flume.pdf", 1),
    ("Kafka 是高吞吐的分布式发布订阅消息队列", "kafka.pdf", 1),
    ("HDFS 是 Hadoop 生态的分布式文件系统，适合一次写入多次读取", "hdfs.pdf", 2),
    ("Spark Core 是 Spark 的核心计算引擎，包含 RDD 弹性分布式数据集", "spark.pdf", 1),
]


def make_chunks() -> list[Chunk]:
    return [
        Chunk(chunk_id=f"doc:{i}", doc_id="doc", filename=fn,
              page=pg, chunk_index=i, content=text)
        for i, (text, fn, pg) in enumerate(CORPUS)
    ]


class TestTokenizer(unittest.TestCase):
    def test_ascii_and_cjk(self):
        tokens = tokenize("Flume 日志采集")
        self.assertIn("flume", tokens)
        self.assertTrue(any("日志" in t for t in tokens))


class TestBM25(unittest.TestCase):
    def test_keyword_match(self):
        store = BM25Store()
        store.build(make_chunks())
        top_id, _ = store.search("日志采集系统", k=1)[0]
        self.assertEqual(top_id, "doc:0")

    def test_english_match(self):
        store = BM25Store()
        store.build(make_chunks())
        top_id, _ = store.search("Kafka 消息队列", k=1)[0]
        self.assertEqual(top_id, "doc:1")

    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "bm25.pkl"
            store = BM25Store()
            store.build(make_chunks())
            store.save(path)
            loaded = BM25Store.load(path)
            self.assertEqual(loaded.chunk_count, 4)
            self.assertEqual(store.search("HDFS 文件系统", k=2),
                             loaded.search("HDFS 文件系统", k=2))


class TestRRF(unittest.TestCase):
    def test_fusion_order(self):
        # 两路列表对 doc:a 的名次均为第 1 → 融合后应排第一
        fused = rrf_fuse([["a", "b", "c"], ["a", "c", "b"]])
        self.assertEqual(max(fused, key=fused.get), "a")

    def test_absent_doc(self):
        fused = rrf_fuse([["a"], ["b"]])
        self.assertNotIn("z", fused)


class TestHybridOffline(unittest.TestCase):
    """FakeEmbeddings（词袋哈希向量）+ 临时目录 Chroma，验证端到端检索链路"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chunks = make_chunks()
        self.vs = VectorStore(FakeEmbeddings(), collection_name="test_hybrid",
                              persist_dir=self.tmp.name)
        self.vs.add_chunks(self.chunks)
        self.bm25 = BM25Store()
        self.bm25.build(self.chunks)
        self.retriever = HybridRetriever(self.vs, self.bm25, reranker=None)

    def tearDown(self):
        self.tmp.cleanup()
        shutil.rmtree(self.tmp.name, ignore_errors=True)

    def test_dense_mode(self):
        hits = self.retriever.retrieve("分布式日志采集系统 Flume", k=1,
                                       mode="dense", use_rerank=False)
        self.assertEqual(hits[0].chunk.chunk_id, "doc:0")
        self.assertEqual(hits[0].stage, "dense")

    def test_bm25_mode(self):
        hits = self.retriever.retrieve("HDFS 分布式文件系统", k=1,
                                       mode="bm25", use_rerank=False)
        self.assertEqual(hits[0].chunk.chunk_id, "doc:2")

    def test_hybrid_mode(self):
        hits = self.retriever.retrieve("Spark RDD 弹性分布式数据集", k=2,
                                       mode="hybrid", use_rerank=False)
        self.assertEqual(hits[0].chunk.chunk_id, "doc:3")
        self.assertEqual(hits[0].stage, "rrf")

    def test_get_all_chunks(self):
        self.assertEqual(len(self.vs.get_all_chunks()), 4)

    def test_delete_document(self):
        self.vs.delete_document("doc")
        self.assertEqual(self.vs.count(), 0)


if __name__ == "__main__":
    unittest.main()
