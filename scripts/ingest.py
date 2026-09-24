"""命令行入库：python scripts/ingest.py 文档1.pdf 文档2.docx ..."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipeline import get_pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="向知识库入库文档（PDF/DOCX/TXT/MD）")
    parser.add_argument("files", nargs="+", help="文档路径")
    parser.add_argument("--rebuild-bm25", action="store_true", help="强制重建 BM25 索引")
    args = parser.parse_args()

    pipeline = get_pipeline()
    if args.rebuild_bm25:
        pipeline.rebuild_bm25()

    for path in args.files:
        p = Path(path)
        if not p.exists():
            print(f"❌ 文件不存在：{p}")
            continue
        result = pipeline.ingest(p.read_bytes(), p.name)
        print(("✅ " if result.success else "❌ ") + f"{p.name}：{result.message}")

    stats = pipeline.stats()
    print(f"\n📊 当前知识库：{stats['documents']} 个文档，{stats['chunks']} 个切片")


if __name__ == "__main__":
    main()
