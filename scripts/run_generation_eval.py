"""生成质量评估：LLM-as-Judge 打忠实度 / 相关性分

用法：python scripts/run_generation_eval.py [--mode hybrid] [--limit 5]
输出：results/generation_eval.md 与 .json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.config import settings  # noqa: E402
from rag.evaluation import evaluate_generation, load_evalset  # noqa: E402
from rag.pipeline import get_pipeline  # noqa: E402
from rag.schemas import AskOptions  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="hybrid", choices=["dense", "bm25", "hybrid"])
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--limit", type=int, default=5, help="评估题目数上限")
    args = parser.parse_args()

    questions = load_evalset()[: args.limit]
    pipeline = get_pipeline()
    options = AskOptions(retrieval_mode=args.mode, use_rerank=not args.no_rerank,
                         rewrite_query=False)

    def answer_fn(question: str):
        result = pipeline.ask(question, options)
        # 引用的上下文按 sources 顺序从 BM25 索引取回
        contexts = [pipeline.bm25.chunks[s.chunk_id].content for s in result.sources]
        return result.answer, contexts

    print(f"生成质量评估：{len(questions)} 题，模式 {args.mode}"
          f"（rerank={'on' if not args.no_rerank else 'off'}）\n")
    metrics = evaluate_generation(questions, answer_fn)

    settings.results_dir.mkdir(exist_ok=True)
    lines = [
        f"# 生成质量评估（{args.mode}，rerank={'on' if not args.no_rerank else 'off'}，n={metrics.n}）",
        "",
        "| 指标 | 得分 |",
        "|---|---|",
        f"| 忠实度 Faithfulness（1-5） | {metrics.faithfulness} |",
        f"| 回答相关性 Relevance（1-5） | {metrics.answer_relevance} |",
        f"| 平均端到端延迟(ms) | {metrics.avg_latency_ms:.0f} |",
        "",
    ]
    (settings.results_dir / "generation_eval.md").write_text(
        "\n".join(lines), encoding="utf-8")
    (settings.results_dir / "generation_eval.json").write_text(
        metrics.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n✅ 忠实度 {metrics.faithfulness}/5，相关性 {metrics.answer_relevance}/5，"
          f"平均延迟 {metrics.avg_latency_ms:.0f} ms")
    print(f"结果已写入 results/generation_eval.md")


if __name__ == "__main__":
    main()
