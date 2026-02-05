# Code RAG - 代码知识库问答系统

基于 RAG（检索增强生成）架构的本地代码知识库问答系统，将项目源码向量化后，通过语义检索 + LLM 生成，实现对代码库的智能问答。

## 系统要求

- macOS / Linux
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai) 已安装并运行

## 快速开始

### 1. 安装 Ollama 并拉取模型

```bash
# macOS 推荐从官网下载 ARM 原生版: https://ollama.com/download
ollama serve  # 启动 Ollama 服务（保持运行）

# 新开终端，拉取所需模型
ollama pull bge-m3               # 向量化模型（多语言支持）
ollama pull qwen2.5-coder:14b    # 代码生成模型
```

### 2. 安装 Python 依赖

```bash
cd code-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动后端服务

```bash
source venv/bin/activate
python -m uvicorn api:app --port 8900 --host 0.0.0.0
```

验证：访问 http://localhost:8900/health ，返回 `{"status":"ok"}` 即成功。

### 4. 启动 Web 前端

```bash
cd web
npm install   # 首次需要
npm run dev
```

访问 http://localhost:5173 即可使用。

### 5. 使用流程

1. 在「训练」页面添加项目（填写项目名称和源码目录路径）
2. 点击「开始索引」，等待索引完成
3. 切换到「Chat」页面，选择已索引的项目
4. 输入代码相关问题，获取 AI 回答

### 6. 命令行模式（可选）

```bash
source venv/bin/activate
python cli.py
```

在终端输入问题，直接获取回答。

## 功能特性

- **多项目管理** — 支持同时管理多个代码项目
- **实时索引进度** — SSE 流式推送索引进度
- **流式问答** — 打字机效果逐字输出回答
- **BM25 + 向量混合重排序** — Rerank 提升检索精度
- **对话历史** — 按项目保存对话记录
- **服务监控** — 查看 Ollama 状态和索引统计

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/projects` | 获取项目列表 |
| POST | `/projects` | 创建项目 |
| POST | `/projects/{id}/index` | 开始索引（SSE 流式进度） |
| POST | `/ask` | 问答（非流式） |
| POST | `/ask/stream` | 问答（流式 SSE） |
| GET | `/monitoring/ollama` | Ollama 服务状态 |
| GET | `/monitoring/stats` | 系统统计 |

### POST /ask/stream

```bash
curl -X POST http://localhost:8900/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "这个项目的主要功能是什么？", "project_id": "xxx", "top_k": 50}'
```

响应（SSE 事件流）：

```
data: {"type": "sources", "data": [{path, module, score}, ...]}
data: {"type": "content", "data": "这个项目"}
data: {"type": "content", "data": "主要实现了..."}
data: {"type": "done"}
```

## 项目结构

```
code-rag/
├── config.py           # 配置中心
├── api.py              # FastAPI 后端服务
├── indexer.py          # 代码扫描 & 向量索引
├── retriever.py        # 语义检索（ChromaDB）
├── generator.py        # LLM 生成
├── reranker.py         # BM25 + 向量混合重排序
├── project_manager.py  # 多项目管理
├── models.py           # Pydantic 数据模型
├── cli.py              # 命令行交互
├── requirements.txt    # Python 依赖
├── data/
│   ├── projects.json   # 项目元数据
│   └── chroma/         # ChromaDB 向量索引
└── web/                # React 前端
    ├── src/
    │   ├── pages/      # Chat / Training / Monitoring
    │   ├── components/ # UI 组件
    │   ├── contexts/   # 全局状态
    │   ├── hooks/      # 自定义 Hook
    │   └── api/        # API 客户端
    ├── package.json
    └── vite.config.js
```

## 配置说明

编辑 `config.py` 可修改以下配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `EMBED_MODEL` | `bge-m3` | 向量化模型 |
| `LLM_MODEL` | `qwen2.5-coder:14b` | LLM 生成模型 |
| `CODE_EXTENSIONS` | `.js .jsx .ts .tsx .less` | 扫描的文件类型 |
| `MAX_FILE_CHARS` | `6000` | 单文件最大字符数 |
| `TOP_K` | `5` | 默认检索结果数 |
| `RERANK_ENABLED` | `True` | 是否开启 Rerank |
| `RERANK_TOP_N` | `8` | Rerank 后保留文档数 |

## 常见问题

**Q: 索引速度很慢？**
A: 向量化依赖 Ollama 本地推理，文件较多时需要一定时间。确保 Ollama 使用 GPU 加速。

**Q: 回答质量不好？**
A: 可尝试：1) 增大 `top_k` 获取更多上下文；2) 换用更大的 LLM 模型；3) 调整 Rerank 权重。

**Q: 端口被占用？**
A: `lsof -ti:8900 | xargs kill -9` 杀掉占用进程后重启。

**Q: macOS 上 Ollama 使用 CPU 而非 GPU？**
A: 确保从 [ollama.com](https://ollama.com/download) 下载 ARM 原生版本，不要使用 Homebrew Intel 版。
