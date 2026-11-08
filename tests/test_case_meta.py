"""离线单元测试：案例元数据（front-matter 解析 / CaseMeta / 存储透传 / 上下文构建，无网络）"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.embeddings import FakeEmbeddings  # noqa: E402
from rag.loaders import load_document_with_meta, parse_front_matter  # noqa: E402
from rag.prompts import build_case_context  # noqa: E402
from rag.registry import DocumentRegistry  # noqa: E402
from rag.schemas import CaseMeta, Chunk, DocInfo, ScoredChunk  # noqa: E402
from rag.vectordb import VectorStore  # noqa: E402

FM_MD = """---
title: 张桂梅与华坪女子高级中学
course: 思想道德与法治
case_type: 人物事迹
knowledge_points: 人生价值、理想信念
related_theory: 马克思主义关于人的价值的理论
---

# 张桂梅

张桂梅创办了全国第一所全免费的公办女子高中。
"""


class TestFrontMatter(unittest.TestCase):
    def test_valid_block(self):
        meta, body = parse_front_matter(FM_MD)
        self.assertEqual(meta["title"], "张桂梅与华坪女子高级中学")
        self.assertEqual(meta["course"], "思想道德与法治")
        self.assertTrue(body.startswith("# 张桂梅"))
        self.assertNotIn("front-matter", body)  # 正文不含元数据块

    def test_no_block(self):
        meta, body = parse_front_matter("普通文档正文")
        self.assertEqual(meta, {})
        self.assertEqual(body, "普通文档正文")

    def test_unclosed_block(self):
        meta, body = parse_front_matter("---\ntitle: x\n正文")
        self.assertEqual(meta, {})
        self.assertIn("title", body)  # 未闭合时原样返回

    def test_bom_and_comment(self):
        meta, body = parse_front_matter("\ufeff---\n# 注释行\nk: v\n---\nbody")
        self.assertEqual(meta, {"k": "v"})
        self.assertEqual(body, "body")

    def test_case_meta_from_front_matter(self):
        meta, _ = parse_front_matter(FM_MD)
        case = CaseMeta.from_front_matter(meta)
        assert case is not None
        self.assertEqual(case.case_title, "张桂梅与华坪女子高级中学")  # title 别名映射
        self.assertEqual(case.knowledge_points, "人生价值、理想信念")

    def test_empty_meta_returns_none(self):
        self.assertIsNone(CaseMeta.from_front_matter({}))


class TestLoadWithMeta(unittest.TestCase):
    def test_md_meta_and_body(self):
        pages, meta = load_document_with_meta(FM_MD.encode("utf-8"), "case.md")
        self.assertEqual(len(pages), 1)
        self.assertEqual(meta["course"], "思想道德与法治")
        self.assertIn("女子高中", pages[0].text)
        self.assertNotIn("front-matter", pages[0].text)  # 元数据不进切片正文

    def test_txt_no_meta(self):
        pages, meta = load_document_with_meta("普通文本。".encode("utf-8"), "a.txt")
        self.assertEqual(meta, {})
        self.assertEqual(pages[0].page, 1)


class TestCaseMetaPassthrough(unittest.TestCase):
    """案例元数据经 VectorStore 写入/读回的完整透传（FakeEmbeddings + 临时目录）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.vs = VectorStore(FakeEmbeddings(), collection_name="test_case_meta",
                              persist_dir=self.tmp.name)
        chunk = Chunk(
            chunk_id="doc:0", doc_id="doc", filename="case.md",
            page=1, chunk_index=0, content="张桂梅创办全国第一所全免费女子高中",
            case_title="张桂梅与华坪女子高级中学", course="思想道德与法治",
            case_type="人物事迹", knowledge_points="人生价值、理想信念",
        )
        self.vs.add_chunks([chunk])

    def tearDown(self):
        self.tmp.cleanup()
        shutil.rmtree(self.tmp.name, ignore_errors=True)

    def test_query_returns_case_fields(self):
        hits = self.vs.query("张桂梅 女子高中", k=1)
        self.assertEqual(hits[0].chunk.case_title, "张桂梅与华坪女子高级中学")
        self.assertEqual(hits[0].chunk.course, "思想道德与法治")
        self.assertEqual(hits[0].chunk.knowledge_points, "人生价值、理想信念")

    def test_get_all_chunks_returns_case_fields(self):
        chunks = self.vs.get_all_chunks()
        self.assertEqual(chunks[0].case_type, "人物事迹")


class TestCaseContextBuild(unittest.TestCase):
    def test_header_with_meta(self):
        hit = ScoredChunk(chunk=Chunk(
            chunk_id="d:0", doc_id="d", filename="f.md", page=1, chunk_index=0,
            content="正文内容",
            case_title="张桂梅与华坪女子高级中学", course="思想道德与法治",
            case_type="人物事迹", knowledge_points="人生价值",
        ))
        ctx = build_case_context([hit])[0]
        self.assertIn("案例《张桂梅与华坪女子高级中学》", ctx)
        self.assertIn("课程：思想道德与法治", ctx)
        self.assertIn("知识点：人生价值", ctx)
        self.assertTrue(ctx.endswith("正文内容"))

    def test_fallback_without_meta(self):
        hit = ScoredChunk(chunk=Chunk(
            chunk_id="d:0", doc_id="d", filename="f.txt", page=1,
            chunk_index=0, content="纯正文",
        ))
        self.assertEqual(build_case_context([hit])[0], "纯正文")


class TestRegistryCase(unittest.TestCase):
    """MySQL 注册表往返测试（专用测试库 sizheng_rag_test，用后即删）"""

    TEST_DB = "sizheng_rag_test"

    @classmethod
    def setUpClass(cls):
        import pymysql as pm
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from rag.config import settings
        from rag.database import Base

        conn = pm.connect(host=settings.mysql_host, port=settings.mysql_port,
                          user=settings.mysql_user,
                          password=settings.mysql_password)
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB}")
            cur.execute(f"CREATE DATABASE {cls.TEST_DB} "
                        "DEFAULT CHARACTER SET utf8mb4")
        conn.commit(); conn.close()

        cls.engine = create_engine(
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{cls.TEST_DB}"
            "?charset=utf8mb4")
        Base.metadata.create_all(cls.engine)
        cls.factory = sessionmaker(bind=cls.engine, expire_on_commit=False)
        # 外键种子：documents.topic_id → topics.id
        from rag.database import Topic
        with cls.factory() as db:
            db.add(Topic(id=1, name="专题一", description="测试"))
            db.add(Topic(id=2, name="专题二", description="测试"))
            db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        import pymysql as pm
        from rag.config import settings
        conn = pm.connect(host=settings.mysql_host, port=settings.mysql_port,
                          user=settings.mysql_user,
                          password=settings.mysql_password)
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {cls.TEST_DB}")
        conn.commit(); conn.close()

    def test_case_roundtrip(self):
        reg = DocumentRegistry(session_factory=self.factory)
        case = CaseMeta(case_title="塞罕坝林场", course="马克思主义基本原理",
                        case_type="实践成果", knowledge_points="人与自然",
                        related_theory="马克思主义自然观")
        reg.add(DocInfo(doc_id="d1", filename="saihanba.md", pages=1,
                        chunks=2, chars=800, case=case,
                        source_info="新华社", topic_id=1))
        loaded = reg.get("d1")
        assert loaded and loaded.case
        self.assertEqual(loaded.case.case_title, "塞罕坝林场")
        self.assertEqual(loaded.case.related_theory, "马克思主义自然观")
        self.assertEqual(loaded.source_info, "新华社")
        self.assertEqual(loaded.topic_id, 1)
        # 无案例元数据的文档
        reg.add(DocInfo(doc_id="d2", filename="plain.txt", pages=1, chunks=1, chars=100))
        self.assertIsNone(reg.get("d2").case)
        # 元数据编辑与专题过滤
        self.assertTrue(reg.update_meta(
            "d2", CaseMeta(case_title="测试案例"), topic_id=2))
        self.assertEqual(reg.list_by_topic(2)[0].doc_id, "d2")
        # 软删除后不可见
        reg.mark_deleted("d1")
        self.assertIsNone(reg.get("d1"))


if __name__ == "__main__":
    unittest.main()
