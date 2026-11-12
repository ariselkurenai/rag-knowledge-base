# 基于检索增强生成的高校思政课程案例研习系统

毕业设计作品：面向高校思政课程教学的 RAG 案例研习平台。教师上传思政案例构建专题案例库，学生通过语义检索与研习问答开展案例学习，AI 回答**标注案例原文出处**（案例名/课程/页码/知识点），教师可对 AI 生成内容进行**审核纠错并全程留痕**。

## 功能特性（对应任务书七大模块）

| 模块 | 说明 |
|---|---|
| ① 用户与权限 | 学生/教师/管理员三角色，JWT 登录，注册（默认学生），接口级角色校验，敏感操作记入审计日志 |
| ② 案例库管理 | 教师上传 PDF/DOCX/TXT/MD，逐页解析 + 中文归一化；元数据双层获取（MD front-matter / LLM 自动抽取兜底）：案例名/课程/类型/知识点/关联理论；归属思政专题（如"思想道德与法治"） |
| ③ 案例分类浏览 | 按专题与课程筛选，卡片展示知识点与理论关联；在线阅读案例原文（切片级定位高亮） |
| ④ 语义检索 | DashScope 向量检索 + 自实现 Okapi BM25 双路召回，RRF 融合，重排序降级链（gte-rerank → LLM 打分 → 原序），可限定专题范围 |
| ⑤ 研习引导问题 | 选中案例 → 大模型生成课堂研习引导问题，自动关联案例原文素材，落库待教师审核 |
| ⑥ 案例研习答疑 | 多轮对话 + 查询改写（指代消解），SSE 流式输出，答案 `[n]` 引用可**回跳原文片段**，展示案例名/课程/知识点 |
| ⑦ 教师审核纠错 | AI 生成内容（答疑/引导问题）全部落库登记；教师可修改内容、补充批注；原始输出不可变，纠错动作追加式记录，形成完整审计链 |
| 评估体系 | Hit@k / MRR / PageRecall@k 检索指标 + LLM-as-Judge 忠实度/相关性打分 + 四配置消融实验脚本 |

## 技术栈

- **后端**：Python 3.11+ / FastAPI / SQLAlchemy / **MySQL**（用户、案例注册表、专题、AI 生成记录、审核日志、审计日志）/ Chroma 向量库（案例切片向量）/ SSE 流式接口
- **前端**：**Vue 3** / Vite / Vue Router / Naive UI（9 个页面：登录注册、案例库、案例阅读、语义检索、研习问答、我的记录、案例管理、审核工作台、用户管理）
- **大模型**：DeepSeek（生成/改写/评测）+ DashScope（Embedding / 重排序），OpenAI 兼容接口
- **工程化**：`.env` 配置、bcrypt 密码哈希、Embedding 磁盘缓存、37 个离线单测、Git 分阶段提交

## 系统架构

```
┌──────────────── Vue 3 前端（Naive UI）────────────────┐
│  学生：案例库/案例阅读/语义检索/研习问答/我的记录        │
│  教师：+ 案例管理/审核工作台    管理员：+ 用户管理       │
└───────────────────────┬───────────────────────────────┘
                        │ JWT / JSON / SSE（Vite 代理）
┌───────────────────────▼───────────────────────────────┐
│                    FastAPI (rag/api/)                  │
│  auth │ users │ topics │ documents │ chat │ review    │
├───────────────────────────────────────────────────────┤
│  MySQL（SQLAlchemy）：users / documents / topics /     │
│  qa_records / review_logs / audit_logs                 │
│  Chroma 向量库：案例切片（含案例元数据）                │
│  BM25 倒排索引（jieba/字符二元组）                     │
├───────────────────────────────────────────────────────┤
│  RAG 管线：解析→切片→双路召回→RRF 融合→重排序降级链     │
│  →资料头注入案例元数据→DeepSeek 流式生成（[n] 引用）   │
└───────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 0) 环境要求：Python 3.11+ / Node 18+ / MySQL 8
#    配置密钥与数据库连接（.env，模板见 .env.example）
#    DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / MYSQL_URL / JWT_SECRET

# 1) 初始化数据库（建库建表 + 种子账号 admin/teacher，密码 123456）
python scripts/init_db.py

# 2) 启动后端（http://127.0.0.1:8000，接口文档 /docs）
python -m rag.server

# 3) 启动前端（http://localhost:5173，首次需 npm install）
cd frontend
npm install
npm run dev

# 4) 入库思政案例（示例语料见 docs/sizheng/）
python scripts/ingest.py docs/sizheng
python scripts/assign_topics.py   # 6 个示例案例分归两个种子专题
```

**审核纠错工作流**：学生提问 → AI 回答落库 `qa_records`（pending）→ 教师在审核工作台修改/批注 → 每次动作追加写入 `review_logs`（含改动前后快照）→ 学生端展示修正后内容与批注。原始 AI 输出永不覆盖，全程可回溯。

## 评估

```bash
python scripts/generate_evalset.py   # 生成评测集（需 DeepSeek 余额）
python scripts/eval_retrieval.py     # 检索消融：dense vs bm25 vs hybrid vs hybrid+rerank
python scripts/run_generation_eval.py  # LLM-as-Judge：忠实度/相关性
```

## 测试

```bash
python -m unittest discover -s tests   # 37 个离线单测（检索/切片/元数据/权限/留痕）
```

## 目录结构

```
rag/            后端核心：database(RAG管线) auth api/ prompts …
frontend/       Vue 3 前端（src/views 9 个页面）
docs/sizheng/   10 个思政示例案例（6 个 MD front-matter 元数据 + 4 个 DOCX LLM 自动抽取元数据）
scripts/        init_db / ingest / 评估脚本
tests/          离线单元测试
```
