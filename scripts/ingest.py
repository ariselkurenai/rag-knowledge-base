"""命令行入库：python scripts/ingest.py 案例1.md 案例2.pdf 目录/ ..."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipeline import get_pipeline  # noqa: E402

INGEST_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def _expand(paths: list[str]) -> list[Path]:
    """展开参数：目录则收录其下全部支持格式的文档（PowerShell 不展开通配符，目录支持必须内置）"""
    out: list[Path] = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            files = sorted(f for f in p.iterdir() if f.suffix.lower() in INGEST_SUFFIXES)
            if not files:
                print(f"⚠️ 目录中没有可入库文档：{p}")
            out.extend(files)
        else:
            out.append(p)
    return out


def main():
    parser = argparse.ArgumentParser(description="向思政案例库入库文档（PDF/DOCX/TXT/MD，支持目录）")
    parser.add_argument("files", nargs="+", help="文档或目录路径")
    parser.add_argument("--topic-id", type=int, default=None,
                        help="归属专题 ID（见 /api/topics，不填则暂不归属）")
    parser.add_argument("--rebuild-bm25", action="store_true", help="强制重建 BM25 索引")
    args = parser.parse_args()

    pipeline = get_pipeline()
    if args.rebuild_bm25:
        pipeline.rebuild_bm25()

    for p in _expand(args.files):
        if not p.exists():
            print(f"❌ 文件不存在：{p}")
            continue
        result = pipeline.ingest(p.read_bytes(), p.name, topic_id=args.topic_id)
        print(("✅ " if result.success else "❌ ") + f"{p.name}：{result.message}")

    stats = pipeline.stats()
    print(f"\n📊 当前案例库：{stats['documents']} 个文档"
          f"（含 {stats['cases']} 个案例、{stats['courses']} 门课程），"
          f"{stats['chunks']} 个切片")


if __name__ == "__main__":
    main()
