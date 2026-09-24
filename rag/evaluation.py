"""评估模块：检索指标 + 生成质量（LLM-as-Judge）

检索指标（对每道评测题，取检索结果的 chunk/page 名次）：
- Hit@k   ：Top-k 中包含金标 chunk 的比例
- MRR     ：金标 chunk 名次的倒数均值
- PageRecall@k：Top-k 中命中金标所在页的比例（页级宽松口径）

生成指标（LLM 裁判，1-5 分）：
- Faithfulness      ：答案是否严格由检索上下文支撑（抗幻觉能力）
- Answer Relevance  ：答案是否回答了问题

配合 scripts/eval_retrieval.py 可做消融实验：
dense vs bm25 vs hybrid vs hybrid+rerank。
"""

import json
import re
import time
from pathlib import Path

from .config import settings
from .llm import ChatLLM, parse_json_reply
from .prompts import FAITHFULNESS_PROMPT, RELEVANCE_PROMPT
from .schemas import (EvalQuestion, GenerationMetrics, RetrievalMetrics,
                      ScoredChunk)


# ── 评测集读写 ──

def load_evalset(path: Path | None = None) -> list[EvalQuestion]:
    path = path or (settings.eval_dir / "evalset.jsonl")
    if not path.exists():
        raise FileNotFoundError(
            f"评测集不存在：{path}\n请先运行 python scripts/generate_evalset.py 生成")
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            questions.append(EvalQuestion(**json.loads(line)))
    return questions


def save_evalset(questions: list[EvalQuestion], path: Path | None = None) -> Path:
    path = path or (settings.eval_dir / "evalset.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q.model_dump(), ensure_ascii=False) + "\n")
    return path


# ── 检索指标 ──

def evaluate_retrieval(questions: list[EvalQuestion],
                       retrieve_fn, mode: str, k: int = 4) -> RetrievalMetrics:
    """retrieve_fn(query, k) -> list[ScoredChunk]，可注入任意检索配置"""
    hits, rr, page_hits, latencies = 0, 0.0, 0, []

    for q in questions:
        t0 = time.perf_counter()
        results: list[ScoredChunk] = retrieve_fn(q.question, k)
        latencies.append((time.perf_counter() - t0) * 1000)

        ranks = [i + 1 for i, r in enumerate(results)
                 if r.chunk.chunk_id == q.expected_chunk_id]
        if ranks:
            hits += 1
            rr += 1.0 / ranks[0]
        if any(r.chunk.filename == q.expected_filename and r.chunk.page == q.expected_page
               for r in results):
            page_hits += 1

    n = len(questions)
    return RetrievalMetrics(
        mode=mode, n=n,
        hit_at_k=round(hits / n, 4), mrr=round(rr / n, 4),
        page_recall_at_k=round(page_hits / n, 4),
        avg_latency_ms=round(sum(latencies) / n, 1) if latencies else 0.0,
    )


def metrics_to_markdown(rows: list[RetrievalMetrics]) -> str:
    header = ("| 检索模式 | Hit@4 | MRR | PageRecall@4 | 平均延迟(ms) | 样本数 |\n"
              "|---|---|---|---|---|---|\n")
    lines = [
        f"| {r.mode} | {r.hit_at_k:.2%} | {r.mrr:.4f} | "
        f"{r.page_recall_at_k:.2%} | {r.avg_latency_ms:.0f} | {r.n} |"
        for r in rows
    ]
    return header + "\n".join(lines) + "\n"


# ── 生成质量（LLM 裁判）──

def judge_scores(llm: ChatLLM, prompt: str) -> tuple[float, str]:
    reply = llm.chat([{"role": "user", "content": prompt}],
                     temperature=0.0, json_mode=True)
    data = parse_json_reply(reply)
    if data and isinstance(data.get("score"), (int, float)):
        return float(data["score"]), str(data.get("reason", ""))
    # 宽容兜底：从文本中抓 1-5 分
    m = re.search(r"[1-5]", reply or "")
    return (float(m.group()) if m else 1.0), "解析失败，采用兜底评分"


def evaluate_generation(questions: list[EvalQuestion], answer_fn,
                        llm: ChatLLM | None = None) -> GenerationMetrics:
    """answer_fn(question) -> (answer, contexts)。返回忠实度与相关性均值"""
    llm = llm or ChatLLM()
    faith, relev, latencies = [], [], []

    for i, q in enumerate(questions):
        t0 = time.perf_counter()
        answer, contexts = answer_fn(q.question)
        latencies.append((time.perf_counter() - t0) * 1000)

        context_text = "\n\n".join(f"【资料 {j}】{c}" for j, c in enumerate(contexts, 1))
        f_score, f_reason = judge_scores(
            llm, FAITHFULNESS_PROMPT.format(context=context_text, answer=answer))
        r_score, _ = judge_scores(
            llm, RELEVANCE_PROMPT.format(question=q.question, answer=answer))
        faith.append(f_score)
        relev.append(r_score)
        print(f"  [{i + 1}/{len(questions)}] 忠实度 {f_score:.0f}/5（{f_reason}），"
              f"相关性 {r_score:.0f}/5")

    n = len(questions)
    return GenerationMetrics(
        n=n,
        faithfulness=round(sum(faith) / n, 2),
        answer_relevance=round(sum(relev) / n, 2),
        avg_latency_ms=round(sum(latencies) / n, 1),
    )
