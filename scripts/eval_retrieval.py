"""检索消融实验：对比 dense / bm25 / hybrid / hybrid+rerank 四种配置

用法：python scripts/eval_retrieval.py [--k 4]
输出：results/retrieval_ablation.md 与 .json

指标：Hit@k、MRR、PageRecall@k、平均检索延迟。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.config import settings  # noqa: E402
from rag.evaluation import (evaluate_retrieval, load_evalset,  # noqa: E402
                            metrics_to_markdown)
from rag.pipeline import get_pipeline  # noqa: E402
from rag.schemas import RetrievalMetrics  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=4, help="Top-k")
    args = parser.parse_args()

    questions = load_evalset()
    pipeline = get_pipeline()
    retriever = pipeline.retriever

    configs = [
        ("dense",         lambda q, k: retriever.retrieve(q, k, mode="dense", use_rerank=False)),
        ("bm25",          lambda q, k: retriever.retrieve(q, k, mode="bm25", use_rerank=False)),
        ("hybrid",        lambda q, k: retriever.retrieve(q, k, mode="hybrid", use_rerank=False)),
        ("hybrid+rerank", lambda q, k: retriever.retrieve(q, k, mode="hybrid", use_rerank=True)),
    ]

    rows: list[RetrievalMetrics] = []
    print(f"评测集：{len(questions)} 题，Top-k = {args.k}\n")
    for name, fn in configs:
        metrics = evaluate_retrieval(questions, fn, mode=name, k=args.k)
        rows.append(metrics)
        print(f"{name:>14}：Hit@{args.k}={metrics.hit_at_k:.2%}  "
              f"MRR={metrics.mrr:.4f}  "
              f"PageRecall={metrics.page_recall_at_k:.2%}  "
              f"延迟={metrics.avg_latency_ms:.0f}ms")

    settings.results_dir.mkdir(exist_ok=True)
    md_path = settings.results_dir / "retrieval_ablation.md"
    md_path.write_text(
        f"# 检索消融实验（n={len(questions)}，Top-{args.k}）\n\n"
        + metrics_to_markdown(rows), encoding="utf-8")
    json_path = settings.results_dir / "retrieval_ablation.json"
    json_path.write_text(
        json.dumps([r.model_dump() for r in rows], ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\n✅ 结果已写入 {md_path} 与 {json_path}")


if __name__ == "__main__":
    main()
