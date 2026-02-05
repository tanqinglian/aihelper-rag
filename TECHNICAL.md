# Code RAG 技术文档

## 1. 架构概览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Web UI     │────→│   FastAPI    │────→│     Ollama       │
│  React+Vite  │ SSE │   api.py     │     │  (本地 LLM 推理)  │
│  :5173       │←────│   :8900      │←────│  :11434          │
└──────────────┘     └──────┬───────┘     └──────────────────┘
                            │                     ↑
                     ┌──────┴───────┐             │
                     │  retriever   │   embedding │
                     │  检索模块     │─────────────┘
                     └──────┬───────┘
                            │ cosine similarity
                     ┌──────┴───────┐
                     │   ChromaDB   │
                     │  向量索引     │
                     └──────────────┘
```

### 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| LLM 推理 | Ollama + qwen2.5-coder:14b | 代码问答生成 |
| 向量化 | Ollama + bge-m3 | 文本转向量（多语言支持） |
| 向量存储 | ChromaDB | 持久化向量索引 |
| 重排序 | BM25 + 向量混合 | Rerank 提升检索精度 |
| 后端 | FastAPI + Uvicorn | REST API + SSE |
| 前端 | React 19 + Vite + Ant Design | Web 交互界面 |

## 2. 核心模块

### 2.1 索引模块 (indexer.py)

负责将源码文件向量化并存入 ChromaDB。

**流程：**

```
source_dir
  │
  ▼
scan_files()          # 递归扫描代码文件
  │                   # 跳过 node_modules/.umi/dist 等目录
  │                   # 截断超过 MAX_FILE_CHARS 的文件
  ▼
get_embedding()       # 调用 Ollama /api/embeddings
  │                   # 拼接 "文件: {path}\n模块: {module}\n{content}" 作为输入
  ▼
ChromaDB              # 存储向量 + 元数据（path, module, sub_module）
```

**关键实现：**

- 模块识别：从文件路径提取 `module`（第一层目录）和 `sub_module`（第二层目录）
- Embedding 输入：拼接文件路径、模块名和内容，增强语义关联
- 错误容忍：单文件 embedding 失败不影响整体索引
- SSE 流式进度：实时推送索引进度到前端

### 2.2 检索模块 (retriever.py)

基于 ChromaDB 的语义检索。

**流程：**

```
用户问题
  │
  ▼
get_embedding(question)    # 问题向量化
  │
  ▼
ChromaDB.query()           # 向量相似度检索
  │
  ▼
[{path, module, content, score}, ...]    # 返回 top_k 结果
```

### 2.3 重排序模块 (reranker.py)

BM25 + 向量相似度混合重排序，提升检索精度。

**流程：**

```
检索结果 (top_k=50)
  │
  ▼
tokenize()                 # jieba 中文分词 + 英文驼峰拆分
  │
  ▼
compute_bm25_score()       # 计算每个文档的 BM25 关键词匹配分数
  │
  ▼
hybrid_score = 0.4 × vector_score + 0.6 × bm25_score    # 混合评分
  │
  ▼
sort + top_n               # 取重排后的 top 8
```

### 2.4 生成模块 (generator.py)

构建 RAG Prompt 并调用 LLM 生成回答。

**Prompt 结构：**

```
System: 你是一个代码知识库助手，负责回答代码相关问题。
        请基于提供的代码片段准确回答问题。如果代码片段不足以回答，请明确说明。

User:   以下是检索到的相关代码：

        --- 文件 1: pages/Example/index.jsx (模块: Example) ---
        {content[:1500]}

        --- 文件 2: ... ---
        {content[:1500]}

        ---

        问题: {question}
```

**流式生成：**

- 调用 Ollama `/api/chat` 接口，设置 `stream: True`
- 使用 `httpx.stream()` 逐行读取 JSON 响应
- 每个 chunk 包含 `{"message": {"content": "..."}}` 字段
- yield 出每个 content 片段

### 2.5 API 服务 (api.py)

**SSE 流式协议：**

```
POST /ask/stream
Content-Type: application/json
{"question": "...", "project_id": "xxx", "top_k": 50}

Response: text/event-stream

data: {"type": "sources", "data": [{path, module, score}, ...]}

data: {"type": "content", "data": "这个功能"}
data: {"type": "content", "data": "主要在..."}

data: {"type": "done"}
```

事件类型：
- `sources` — 检索到的参考文件列表（流开始时发送一次）
- `content` — LLM 生成的文本片段（持续发送）
- `done` — 流结束信号

### 2.6 前端

**三页面架构：**

| 页面 | 路由 | 功能 |
|------|------|------|
| Chat | `/chat` | 代码问答对话 |
| Training | `/training` | 项目管理与索引训练 |
| Monitoring | `/monitoring` | 服务状态监控 |

**流式消费实现：**

```javascript
const reader = res.body.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  const chunk = decoder.decode(value, { stream: true })
  // 解析 SSE data: 行，按 type 分发处理
}
```

## 3. 数据流

### 完整问答流程

```
用户输入问题
     │
     ▼
[前端] POST /ask/stream ──→ [API] ──→ [Retriever]
                                          │
                                 ChromaDB.query()
                                 return top_k=50 docs
                                          │
                              ←────────────┘
                              │
                     [Reranker] BM25 + Vector 混合排序
                        top_n=8 docs
                              │
                     SSE: sources event ──→ [前端] 显示参考文件
                              │
                     [Generator]
                        build prompt (system + docs + question)
                        stream call Ollama /api/chat
                              │
                     SSE: content chunks ──→ [前端] 逐字显示
                              │
                     SSE: done ──→ [前端] 完成渲染
```

## 4. 性能与限制

| 指标 | 当前值 | 说明 |
|------|--------|------|
| 单文件上限 | 6000 字符 | 超出截断 |
| 检索数量 | top_k=50 | 初始检索文档数 |
| Rerank 保留 | top_n=8 | 重排后保留的文档数 |
| LLM 超时 | 600s | 本地模型推理 |
| 向量维度 | 1024 | bge-m3 输出维度 |

### 当前限制

1. **文件级粒度** — 以整个文件为检索单位，未做函数级切片
2. **无增量索引** — 每次索引全量重建
3. **Rerank 为 BM25** — 受 Python 3.14 限制无法使用 Cross-Encoder 模型

## 5. 扩展方向

| 方向 | 实现方式 |
|------|----------|
| 函数级切片 | 用 AST 解析器按函数/组件拆分文件 |
| Cross-Encoder Rerank | 等 Python 3.14 生态完善后引入 bge-reranker 模型 |
| 增量索引 | 比对文件 hash，仅索引变更文件 |
| 更大模型 | 换用 qwen2.5-coder:32b 或 deepseek-coder |
| 多轮对话 | 在 generator 中维护 message history |
| 文档索引 | 支持 .md/.doc 等产品文档 |
