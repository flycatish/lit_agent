# 文献智能检索 Agent

基于 [文献智能检索Agent.md](../文献智能检索Agent.md) 设计的可用 demo。

6 阶段编排：**Planner → Retriever → Reranker → Reader → Reflector → Synthesizer**，带反思闭环（证据不足时自动补检）。

## 快速启动

```bash
cd D:\document\projects\教程\lit_agent

# 首次：建 venv 并装依赖（机器上有多个 Python，务必显式指定 3.12）
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# 启动（显式用 venv 的 python，不受 PATH 中 Python 版本影响）
venv\Scripts\python.exe -m streamlit run app.py
```

浏览器打开 `http://localhost:8501`，输入研究问题即可。

> **多 Python 版本的坑**：裸命令 `pip` / `streamlit` 指向 PATH 里第一个 Python（本机是 3.10），依赖会装错地方导致启动失败。一律用 `venv\Scripts\python.exe -m ...`，无需激活 venv。

## 架构

```
用户问题
   ↓
[Planner]     LLM 拆解为 3-6 个子查询 + 分配数据源
   ↓
[Retriever]   并行检索 arXiv / PubMed / Semantic Scholar（源间并行、源内串行避免限流）
   ↓
[Reranker]    LLM 打分 0-10，保留 Top-K
   ↓
[Reader]      LLM 批量阅读摘要，提取 findings/method/limitations/verbatim citations
   ↓
[Reflector]   LLM 自评证据充分性、gaps、conflicts；不足则生成补检子查询 ←┐
   ↓  (不足回到 Retriever，最多 N 轮)                                   │
[Synthesizer] LLM 生成 Markdown 综述（Overview/Findings/对比表/References）│
   ↓                                                                     │
   ←─────────────────────────────────────────────────────────────────────┘
```

## LLM 接入

直接调用 hap-gateway 的 OpenAI 兼容 API。`config.py` 启动时自动读取 `~/.config/opencode/opencode.jsonc`（baseURL / apiKey / X-Codehub-Token / temperature，模型跟随 opencode 顶层 `model` 字段），opencode 里换模型后本应用**零改动**自动跟随：

- **endpoint / 认证凭证**: 内网地址与 key/token 属敏感信息，统一放 `.env`（见 `.env.example` 说明），代码与文档中不落盘
- **model**: 自动取自 opencode 默认模型（当前 `GLM5-FP8-IT`）
- **认证**: `Authorization: Bearer {apiKey}` + `X-Codehub-Token` header（值为 `.env` 中的 `LIT_LLM_API_KEY` / `LIT_LLM_AUTH_TOKEN`）
- **关键**: `trust_env=False` 绕过系统代理直连内网 API

配置优先级：`.env` / 环境变量（`LIT_LLM_*`）> `opencode.jsonc` > 空。内网 endpoint 与凭证只放 `.env`；`.env` 不存在时回退 opencode.jsonc（凭证齐全同样能跑），参考 `.env.example`。

## 数据源

| 源 | 端点 | 限流处理 |
|----|------|---------|
| arXiv | `export.arxiv.org/api/query` | User-Agent + 429 重试 |
| PubMed | `eutils.ncbi.nlm.nih.gov` (esearch+efetch) | 3 req/s sleep |
| Semantic Scholar | `api.semanticscholar.org` | 1 req/s + 429 重试 |

全部无需 API key。`verify=False` 跳过企业代理的 SSL 证书问题。

## 扩展点

| 想加什么 | 怎么做 |
|---------|--------|
| 新数据源 | `sources/` 加文件实现 `SourceBase.search()`，在 `sources/__init__.py` 注册 |
| 换 LLM | 改 `.env` 的 `LIT_LLM_*` 字段，0 代码改动 |
| 换 Reranker 策略 | 替换 `stages/reranker.py` 的 `run()`，签名不变 |
| 加全文解析 | `sources/` 加 PDF 下载器，`stages/reader.py` 改读全文 |
| 调整反思轮数 | UI 侧边栏滑块或 `.env` 的 `LIT_MAX_REFLECT_ROUNDS` |

## 目录结构

```
lit_agent/
├── config.py             # pydantic-settings 配置
├── app.py                # Streamlit UI（时间线 / 论文卡片 / 综述）
├── llm/client.py         # OpenAI 兼容 API 客户端（chat + chat_json）
├── core/
│   ├── agent.py          # 主编排循环 + 并行检索
│   ├── state.py          # AgentState（去重、索引）
│   └── types.py          # Paper / SubQuery / ScoredPaper / ReadingNote / Reflection
├── sources/              # 数据源插件（统一 SourceBase 接口）
│   ├── base.py
│   ├── arxiv.py
│   ├── pubmed.py
│   └── semantic_scholar.py
└── stages/               # 5 个阶段，每个独立可替换
    ├── planner.py        # 拆子查询
    ├── reranker.py       # Top-K 筛选
    ├── reader.py         # 摘要阅读（分批 5 篇）
    ├── reflector.py      # 自评 + 补检决策
    └── synthesizer.py    # Markdown 综述生成
```

## 已知限制

- **仅摘要**：全文获取受订阅限制，Reader 只读摘要
- **延迟 1-3 分钟**：多轮 LLM + 多源检索，UI 用时间线缓解等待
- **数据源限流**：arXiv/S2 短时间多次请求会 429，代码内有重试但可能仍失败
- **citation 需人工核验**：LLM 标的引用不一定完全对齐原文
