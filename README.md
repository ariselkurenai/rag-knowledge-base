# 基于 RAG 的私有知识库问答系统

面向毕业设计的检索增强生成（RAG）完整实现：多格式文档入库、**混合检索（向量 + BM25 + RRF 融合）**、
**重排序降级链**、多轮对话与查询改写、流式生成与**引用溯源**、以及一套可复现的**评估与消融实验**体系。

## 功能特性

| 模块 | 说明 |
|---|---|
| 多格式入库 | PDF / DOCX / TXT / MD，逐页解析 + 中文归一化（修复 PDF 汉字间空格） |
| 中文感知切片 | 递归切分（段落→句→分句号）+ 碎片合并 + 重叠回看，保留页码元数据 |
| 混合检索 | DashScope `text-embedding-v4` 稠密检索 + **自实现 Okapi BM25**（jieba/字符二元组分词）+ RRF 融合 |
| 重排序降级链 | DashScope `gte-rerank` 交叉编码 → DeepSeek LLM listwise 打分 → 原序兜底，任何一级失败不阻塞主流程 |
| 多轮对话 | 会话记忆 + LLM 查询改写（把「它/这个」展开为独立问题再检索） |
| 引用溯源 | 答案中 `[n]` 标注，回答后列出被引用的文档名与页码 |
| 流式输出 | SSE（FastAPI）与生成器（Gradio）双通道，含首字延迟统计 |
| 评估体系 | Hit@k / MRR / PageRecall@k 检索指标 + LLM-as-Judge 忠实度/相关性打分 + 四配置消融实验脚本 |
| 工程化 | `.env` 配置管理、Embedding 磁盘缓存（重复入库不计费）、SQLite 文档注册表、24 个离线单测 |

## 系统架构

```
┌─────────────┐   ┌─────────────────────────── 离线索引 ───────────────────────────┐
│ 文档上传      │   │  PDF/DOCX/TXT/MD 解析 → 中文归一化 → 递归切片(带页码)           │
│ (Web/API/CLI)│──▶│      │                                    │                    │
└─────────────┘   │      ▼ (embedding 磁盘缓存)               ▼                    │
                   │  DashScope Embedding              BM25 倒排索引                │
                   │      ▼                                    │                    │
                   │  Chroma 向量库  ◄────── 单副本真源 ──────┘                    │
                   │                                    SQLite 文档注册表            │
                   └────────────────────────────────────────────────────────────────┘
┌─────────────────────────── 在线问答 ───────────────────────────┐
│  用户提问                                                      │
│    ▼ 会话记忆(多轮) → LLM 查询改写(指代消解)                      │
│    ▼ 双路召回: Dense(Chroma) + Sparse(BM25)                     │
│    ▼ RRF 融合  score(d)=Σ 1/(k+rank)                           │
│    ▼ 重排序降级链: gte-rerank → LLM 打分 → 原序                  │
│    ▼ DeepSeek 流式生成(带[n]引用) → 引用解析 → 来源/延迟统计      │
└────────────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 0) 配置密钥（.env 已被 .gitignore 排除，模板见 .env.example）
#    DEEPSEEK_API_KEY / DASHSCOPE_API_KEY

# 1) 入库文档
python app.py ingest docs/test.pdf

# 2) 命令行问答
python app.py ask "Flume 的基础架构包含哪些组件？"

# 3) 网页界面（Gradio，http://127.0.0.1:7860）
python app.py web

# 4) REST API 服务（http://127.0.0.1:8000，含 /docs 交互文档）
python app.py serve
```

### REST API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/documents` | 上传文档（multipart） |
| GET / DELETE | `/api/documents` `/api/documents/{id}` | 文档列表 / 删除 |
| POST | `/api/sessions` | 新建多轮会话 |
| POST | `/api/chat` | 问答；`stream: true` 返回 SSE 事件流（sources → delta… → done） |
| GET | `/api/stats` `/api/health` | 知识库统计 / 健康检查 |

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Event 由哪几部分组成？", "retrieval_mode": "hybrid", "top_k": 4}'
```

## 评估与消融实验（论文实验章素材）

```bash
# ① 从知识库自动生成评测集（LLM 出题：仅凭单切片可答 + 金标答案 + 期望页码）
python scripts/generate_evalset.py --num 10

# ② 检索消融：dense / bm25 / hybrid / hybrid+rerank 四配置对比
python scripts/eval_retrieval.py --k 4

# ③ 生成质量：LLM-as-Judge 忠实度(抗幻觉) + 回答相关性
python scripts/run_generation_eval.py --limit 5
```

### 实测结果（docs/test.pdf，8 页 Flume 资料，自动生成 6 题，Top-4）

| 检索模式 | Hit@4 | MRR | PageRecall@4 | 平均延迟 |
|---|---|---|---|---|
| dense | 100% | 0.8750 | 100% | 393 ms |
| bm25 | 100% | 1.0000 | 100% | ~0 ms |
| hybrid | 100% | 0.9167 | 100% | 3 ms |
| hybrid+rerank | 100% | 1.0000 | 100% | 6343 ms* |

生成质量（4 题）：忠实度 **5.0/5**，回答相关性 **5.0/5**，平均端到端延迟 8.5 s。

> *重排序延迟包含了 gte-rerank 不可用时的 LLM 打分降级（一次 LLM 调用）。
> 当前语料仅 8 页、任务偏易，各模式 Hit 均饱和；**建议毕设答辩前入库更大语料**
> （如整本教材、多份 PDF，100+ 页），才能观察出各模式的显著差异——这正是消融
> 实验的意义所在。扩大语料后重新跑三个脚本即可自动刷新 `results/` 下的报告。

## 目录结构

```
├── app.py                  # CLI 入口（ingest/ask/stats/serve/web）
├── rag/                    # 核心包
│   ├── config.py           # .env 配置（pydantic-settings）
│   ├── schemas.py          # 统一数据模型
│   ├── loaders.py          # 多格式解析 + 中文归一化
│   ├── chunking.py         # 递归切片 + 引用解析
│   ├── embeddings.py       # DashScope 向量 + 磁盘缓存 + FakeEmbeddings(测试)
│   ├── vectordb.py         # Chroma 封装（模型指纹校验/文档级删除）
│   ├── bm25.py             # 自实现 Okapi BM25 + 中文分词 + 持久化
│   ├── rerank.py           # 重排序降级链（gte-rerank → LLM 打分 → 原序）
│   ├── retrieval.py        # 双路召回 + RRF 融合
│   ├── llm.py              # DeepSeek 客户端（同步/流式/JSON）
│   ├── prompts.py          # 提示词模板集中管理
│   ├── memory.py           # 会话记忆
│   ├── registry.py         # SQLite 文档注册表
│   ├── pipeline.py         # 管线编排（入库/问答/流式/延迟统计）
│   ├── evaluation.py       # 检索指标 + LLM 裁判
│   └── server.py           # FastAPI（REST + SSE）
├── front/app.py            # Gradio 界面（文档管理 + 参数面板 + 流式问答）
├── scripts/                # ingest / 评测集生成 / 消融实验 / 生成评估
├── tests/                  # 24 个离线单测（不依赖网络与真实密钥）
├── data/  cache/  results/ # 运行时数据 / 向量缓存 / 实验报告
└── chroma_db/              # 向量库持久化
```

## 测试

```bash
python -m unittest discover -s tests -v    # 24 个离线单测，无需网络
```

覆盖：中文归一化、切片属性与页码保持、BM25 关键词匹配与索引持久化、RRF 融合
顺序、引用编号解析、JSON 宽容解析、FakeEmbeddings 端到端混合检索、文档删除。

## 毕设写作建议

- **系统设计章**：按「离线索引 / 在线问答」两阶段讲架构图；重点设计点——
  混合检索为何比单一稠密检索稳（语义 vs 关键词互补）、RRF 只用名次融合的鲁棒性、
  重排序降级链的可用性设计、查询改写解决多轮指代失焦。
- **实验章**：先用 `generate_evalset.py` 说明评测集构建方法（可复现），
  再用 `eval_retrieval.py` 做检索消融、`run_generation_eval.py` 做生成质量评估；
  语料扩大后各组差异会显现，可补充 chunk_size/k/rerank 的敏感性实验。
- **可选扩展**：Milvus 替换 Chroma、加入查询多路扩展（Multi-Query）、
  语义缓存、答案高亮定位（页码已具备）。

## 安全提示

`.env` 中的 API Key 已从源码中移出并加入 `.gitignore`。若旧版本代码曾连同密钥
一起提交/分享过，请到 DeepSeek 与阿里云百炼控制台**作废并重置**这些密钥。
