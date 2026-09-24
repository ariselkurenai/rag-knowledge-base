"""提示词模板：RAG 回答 / 查询改写 / 评估裁判 / 评测集生成"""

# ── 知识库问答 ──

RAG_SYSTEM_PROMPT = """你是严谨的知识库问答助手。请仅依据用户消息中提供的【参考资料】回答问题，并遵守：
1. 回答中必须用 [n] 标注所用资料编号，例如「Flume 是分布式日志采集系统[1]」；
2. 若参考资料不足以回答，明确说明「知识库中没有足够的相关信息」，禁止编造；
3. 使用中文回答，条理清晰，复杂内容分点陈述；
4. 保留资料中的数字、术语与专有名词原文，不要臆测。"""


def build_rag_user_prompt(question: str, contexts: list[str]) -> str:
    refs = "\n\n".join(
        f"【资料 {i}】\n{content}" for i, content in enumerate(contexts, start=1)
    )
    return f"{refs}\n\n【问题】\n{question}"


# ── 多轮查询改写 ──

CONDENSE_SYSTEM_PROMPT = """你是多轮对话中的问题改写器。请把用户最新提问结合历史对话改写为一句**独立、完整、可脱离上下文理解**的问题。
规则：
- 若最新提问本身已经完整，原样输出即可；
- 指代词（它、这个、上述等）必须展开为具体对象；
- 只输出改写后的问题本身，不要任何解释。"""


def build_condense_prompt(history: list[dict], question: str) -> list[dict]:
    lines = []
    for msg in history[-6:]:
        role = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{role}：{msg['content']}")
    return [
        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
        {"role": "user", "content": f"【历史对话】\n{''.join(lines) or '（无）'}\n\n【最新提问】\n{question}"},
    ]


# ── LLM 评估裁判 ──

FAITHFULNESS_PROMPT = """你是 RAG 系统的评估裁判。请判断【回答】是否严格由【参考资料】支撑，不存在资料之外的编造或补充。
评分标准（1-5）：
5 = 完全由资料支撑；4 = 基本支撑，个别措辞超出资料但无害；
3 = 部分支撑；2 = 大量内容超出资料；1 = 基本与资料无关或编造。

【参考资料】
{context}

【回答】
{answer}

请输出 JSON：{{"score": 1-5, "reason": "一句话理由"}}"""


RELEVANCE_PROMPT = """你是 RAG 系统的评估裁判。请判断【回答】是否切中了【问题】的提问意图。
评分标准（1-5）：
5 = 完整回答了问题；4 = 基本回答但略有遗漏；3 = 部分回答；
2 = 答非所问的成分居多；1 = 完全没有回答问题。

【问题】
{question}

【回答】
{answer}

请输出 JSON：{{"score": 1-5, "reason": "一句话理由"}}"""


# ── 评测集自动生成 ──

EVALSET_GEN_PROMPT = """你是 RAG 评测集构建器。请根据下面的【资料片段】出一道知识问答题，要求：
1. 问题必须**仅凭该片段即可回答**，且具体到事实层面（定义、数字、组件名、流程等）；
2. 问题中至少包含片段里的一个关键词，模拟真实检索场景；
3. 答案简洁准确，不超过 80 字；
4. 不要出「这段话讲了什么」类的泛化问题。

【资料片段】
{chunk}

请输出 JSON：{{"question": "...", "answer": "..."}}"""


# ── LLM 重排序（DashScope gte-rerank 不可用时的降级方案）──

LLM_RERANK_PROMPT = """你是检索结果重排序器。请判断每条【候选资料】对【查询】的回答价值，逐条打分（0-10）：
10 = 直接包含答案；6-9 = 高度相关；3-5 = 部分相关；0-2 = 无关。

【查询】
{query}

【候选资料】
{documents}

只输出 JSON：{{"scores": [候选1得分, 候选2得分, ...]}}，顺序与输入严格一致。"""


def build_llm_rerank_docs(candidates: list[str], max_chars: int = 600) -> str:
    """候选文档截断后编号罗列，控制 prompt 长度"""
    return "\n".join(
        f"[{i}] {text[:max_chars]}..." if len(text) > max_chars else f"[{i}] {text}"
        for i, text in enumerate(candidates, start=1)
    )
