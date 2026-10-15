"""提示词模板：思政案例研习回答 / 元数据抽取 / 查询改写 / 评估裁判 / 评测集生成"""

# ── 案例研习问答 ──

RAG_SYSTEM_PROMPT = """你是高校思政课程案例研习系统的问答助手，帮助学生结合具体案例研习思政课的理论与知识。请仅依据用户消息中提供的【参考资料】（案例与课程资料）回答问题，并遵守：
1. 回答中必须用 [n] 标注所用资料编号，例如「张桂梅坚守滇西贫困山区教育一线四十余年[1]」；
2. 将案例事实与思政课的理论观点结合起来分析，做到理论联系实际；理论表述须以参考资料为依据，不得凭空引入资料之外的观点或拔高发挥；
3. 若参考资料不足以回答，明确说明「案例库中没有足够的相关信息」，禁止编造；
4. 使用中文回答，语言庄重准确、条理清晰，符合思政课程的话语体系，复杂内容分点陈述；
5. 保留资料中的时间、数字、人名、术语与专有名词原文，不要臆测。"""


def build_case_context(hits) -> list[str]:
    """把检索命中组装为带案例元数据头的资料文本（元数据缺失时退化为纯内容）"""
    contexts = []
    for h in hits:
        c = h.chunk
        bits = []
        if c.case_title:
            bits.append(f"案例《{c.case_title}》")
        if c.course:
            bits.append(f"课程：{c.course}")
        if c.case_type:
            bits.append(f"类型：{c.case_type}")
        if c.knowledge_points:
            bits.append(f"知识点：{c.knowledge_points}")
        header = f"（{' · '.join(bits)}）\n" if bits else ""
        contexts.append(header + c.content)
    return contexts


def build_rag_user_prompt(question: str, contexts: list[str]) -> str:
    refs = "\n\n".join(
        f"【资料 {i}】\n{content}" for i, content in enumerate(contexts, start=1)
    )
    return f"{refs}\n\n【问题】\n{question}"


# ── 案例元数据自动抽取（PDF/DOCX 等无 front-matter 文档的兜底）──

CASE_META_EXTRACT_PROMPT = """你是思政课程案例库的元数据抽取器。请阅读下面的【文档内容】，抽取案例元数据，用于案例库的分类管理。

要求：
1. case_title：案例名称，简明扼要（如「张桂梅与华坪女子高级中学」）；若文档并非单一案例，用文档主题命名；
2. course：所属思政课程，从以下选项中选择最贴切的一个：思想道德与法治、马克思主义基本原理、毛泽东思想和中国特色社会主义理论体系概论、习近平新时代中国特色社会主义思想概论、中国近现代史纲要、形势与政策；无法判断时填「通用」；
3. case_type：案例类型，从以下选项中选择：人物事迹、时政热点、法治案例、历史事件、实践成果；
4. knowledge_points：该案例对应的知识点，用顿号分隔，2-5 个（如「人生价值、理想信念」）；
5. related_theory：关联的教材理论或原理，一句话概括（如「马克思主义关于人的价值的理论」）。

【文档内容】
{content}

请输出 json：{{"case_title": "...", "course": "...", "case_type": "...", "knowledge_points": "...", "related_theory": "..."}}"""


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

FAITHFULNESS_PROMPT = """你是思政案例研习系统的评估裁判。请判断【回答】是否严格由【参考资料】（案例与课程资料）支撑，不存在资料之外的编造或补充。
评分标准（1-5）：
5 = 完全由资料支撑；4 = 基本支撑，个别措辞超出资料但无害；
3 = 部分支撑；2 = 大量内容超出资料；1 = 基本与资料无关或编造。

【参考资料】
{context}

【回答】
{answer}

请输出 JSON：{{"score": 1-5, "reason": "一句话理由"}}"""


RELEVANCE_PROMPT = """你是思政案例研习系统的评估裁判。请判断【回答】是否切中了【问题】的提问意图。
评分标准（1-5）：
5 = 完整回答了问题；4 = 基本回答但略有遗漏；3 = 部分回答；
2 = 答非所问的成分居多；1 = 完全没有回答问题。

【问题】
{question}

【回答】
{answer}

请输出 JSON：{{"score": 1-5, "reason": "一句话理由"}}"""


# ── 评测集自动生成 ──

EVALSET_GEN_PROMPT = """你是思政课程案例研习系统的评测集构建器。请根据下面的【资料片段】出一道案例研习问答题，要求：
1. 问题必须**仅凭该片段即可回答**，且具体到事实层面（时间、人物、事件、数据、理论要点等）；
2. 问题应引导学生把案例事实与思政理论联系起来，且问题中至少包含片段里的一个关键词，模拟真实检索场景；
3. 答案简洁准确，不超过 80 字；
4. 不要出「这段话讲了什么」类的泛化问题。

【资料片段】
{chunk}

请输出 JSON：{{"question": "...", "answer": "..."}}"""


# ── LLM 重排序（DashScope gte-rerank 不可用时的降级方案）──

LLM_RERANK_PROMPT = """你是检索结果重排序器。请判断每条【候选资料】（案例与课程资料）对【查询】的回答价值，逐条打分（0-10）：
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
