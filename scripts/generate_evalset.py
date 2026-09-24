"""自动生成评测集：从知识库切片中抽样，用 LLM 生成「问题 + 金标答案」

用法：python scripts/generate_evalset.py [--num 10] [--seed 42]
输出：data/eval/evalset.jsonl

评测集质量规则：问题必须仅凭该切片可答、包含切片关键词、答案为事实层面。
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.config import settings  # noqa: E402
from rag.evaluation import save_evalset  # noqa: E402
from rag.llm import ChatLLM, parse_json_reply  # noqa: E402
from rag.pipeline import get_pipeline  # noqa: E402
from rag.prompts import EVALSET_GEN_PROMPT  # noqa: E402
from rag.schemas import EvalQuestion  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=10, help="生成题目数")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-chunk-len", type=int, default=200,
                        help="参与抽样的切片最小长度")
    args = parser.parse_args()

    pipeline = get_pipeline()
    chunks = [c for c in pipeline.vs.get_all_chunks() if len(c.content) >= args.min_chunk_len]
    if not chunks:
        print("❌ 知识库为空或没有足够长的切片，请先运行 scripts/ingest.py")
        sys.exit(1)

    # 按页去重抽样（同页切片信息重叠，浪费评测预算）
    by_page: dict[tuple, list] = {}
    for c in chunks:
        by_page.setdefault((c.doc_id, c.page), []).append(c)
    pages = sorted(by_page.keys())
    random.Random(args.seed).shuffle(pages)

    selected = []
    for key in pages[: args.num]:
        # 每页选最长的一个切片（信息密度最高）
        selected.append(max(by_page[key], key=lambda c: len(c.content)))

    llm = ChatLLM()
    questions: list[EvalQuestion] = []
    for i, chunk in enumerate(selected):
        prompt = EVALSET_GEN_PROMPT.format(chunk=chunk.content)
        data = parse_json_reply(llm.chat([{"role": "user", "content": prompt}],
                                         temperature=0.3, json_mode=True))
        if not data or not data.get("question") or not data.get("answer"):
            print(f"  [{i + 1}] ⚠️ 生成失败，跳过（page {chunk.page}）")
            continue
        questions.append(EvalQuestion(
            question=data["question"].strip(),
            answer=data["answer"].strip(),
            expected_chunk_id=chunk.chunk_id,
            expected_filename=chunk.filename,
            expected_page=chunk.page,
        ))
        print(f"  [{i + 1}/{len(selected)}] 第 {chunk.page} 页：{questions[-1].question}")

    if not questions:
        print("❌ 未能生成任何题目")
        sys.exit(1)

    path = save_evalset(questions)
    print(f"\n✅ 评测集已生成：{path}（{len(questions)} 题）")


if __name__ == "__main__":
    main()
