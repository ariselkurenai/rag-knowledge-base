"""离线单元测试：文本归一化 / 切片 / 引用解析 / JSON 解析（无网络依赖）"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.chunking import parse_citations, split_pages  # noqa: E402
from rag.llm import parse_json_reply  # noqa: E402
from rag.loaders import normalize_text  # noqa: E402
from rag.schemas import PageContent  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_removes_cjk_spaces(self):
        # PDF 提取常见问题：汉字之间插入空格
        self.assertEqual(normalize_text("Flume 是  Cloudera 提供的"), "Flume 是 Cloudera 提供的")

    def test_keeps_english_spaces(self):
        self.assertEqual(normalize_text("high available system"), "high available system")

    def test_collapses_blank_lines(self):
        self.assertEqual(normalize_text("a\n\n\n\nb"), "a\n\nb")


class TestChunking(unittest.TestCase):
    def _pages(self):
        para = "Flume 是一个分布式日志采集系统。它可以实时读取服务器本地磁盘的数据，将数据写入 HDFS。"
        return [PageContent(page=i, text=para * 20) for i in range(1, 4)]

    def test_basic_properties(self):
        chunks = split_pages(self._pages(), "doc1", "doc1.pdf")
        # 每页约 900 字、chunk_size=800 → 每页至少 2 块
        self.assertTrue(len(chunks) >= 6)
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)), "chunk_id 必须唯一")
        for c in chunks:
            self.assertEqual(c.filename, "doc1.pdf")
            self.assertGreater(len(c.content), 50)
            # 允许小碎片合并带来的少量超长
            self.assertLess(len(c.content), 1200)

    def test_page_metadata_preserved(self):
        chunks = split_pages(self._pages(), "doc1", "doc1.pdf")
        pages = sorted({c.page for c in chunks})
        self.assertEqual(pages, [1, 2, 3])

    def test_short_page_single_chunk(self):
        pages = [PageContent(page=7, text="HDFS 是分布式文件系统。")]
        chunks = split_pages(pages, "d", "x.pdf")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page, 7)


class TestCitations(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_citations("Flume 是系统[1]，组件有[2]和[3]"), {1, 2, 3})

    def test_none(self):
        self.assertEqual(parse_citations("没有任何引用"), set())

    def test_dedup(self):
        self.assertEqual(parse_citations("同一来源[2]引用两次[2]"), {2})


class TestJsonParse(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_json_reply('{"score": 5}'), {"score": 5})

    def test_fenced(self):
        self.assertEqual(parse_json_reply('```json\n{"score": 3}\n```'), {"score": 3})

    def test_with_prose(self):
        self.assertEqual(parse_json_reply('好的，结果如下：{"score": 4} 请查收'),
                         {"score": 4})

    def test_invalid(self):
        self.assertIsNone(parse_json_reply("完全不是 JSON"))


if __name__ == "__main__":
    unittest.main()
