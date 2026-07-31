"""
DesignAgent - 需求 → 详细设计文档（Function Calling 版）

输入：产品需求文本
输出：结构化详细设计文档（含待确认问题 TODO 清单）
"""
import json
from typing import Generator

import httpx

from config import LLM_PROVIDER, ZHIPU_API_KEY, ZHIPU_BASE_URL, ZHIPU_LLM_MODEL, OLLAMA_BASE_URL, LLM_MODEL
from retriever import retrieve_by_project, retrieve_by_path
from models import AgentStep


SYSTEM_PROMPT = """你是一名技术架构师，任务是基于【真实代码检索结果】生成详细设计文档。

## 严格要求
- 所有文件路径、函数名、接口路径必须来自工具返回的真实结果，禁止凭空编造
- 必须先搜索代码再生成文档：search_frontend → search_backend → get_file（至少读 2 个文件）→ 追加搜索 → 生成
- 遇到不确定的地方写 <!-- TODO -->，不要猜测

## 分析步骤
1. 从需求提取关键词（中英文都要）
2. search_frontend：搜索前端相关页面和组件
3. search_backend：搜索后端相关接口和 Service
4. get_file：读取核心文件完整内容（至少 2 个）
5. 追加搜索相关模块（如发现新线索）
6. 生成完整设计文档（停止工具调用，直接输出文档）

## 最终输出格式（完成所有搜索后输出）

# 详细设计：{需求标题}

## 一、待确认问题
> 基于代码现状发现的疑问，需向产品确认

1. **[问题]**：现有代码中 XXX，需求未说明是否需要 YYY <!-- TODO -->

（无疑问则写"无"）

## 二、需求理解
[复述需求核心点，1-3 句话]

## 三、影响范围

### 前端文件
| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| 真实的文件路径 | 新增/修改 | 具体改什么 |

### 后端文件
| 文件路径 | 改动类型 | 说明 |
|---------|---------|------|
| 真实的文件路径 | 新增/修改 | 具体改什么 |

## 四、接口设计
[新增或修改的接口，含请求/响应字段]

## 五、前端实现方案
[基于真实代码，说明具体改动]

## 六、后端实现方案
[基于真实代码，说明具体改动]

## 七、实现步骤
1. [步骤]（难度：简单/中等/复杂）
"""

# Function Calling 工具定义（OpenAI 兼容格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_frontend",
            "description": "在前端代码库（React/TypeScript）中语义搜索相关文件、页面和组件",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，英文效果更好，如：reschedule apply, conflict modal"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 8",
                        "default": 8
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_backend",
            "description": "在后端 Java 代码库中语义搜索相关 Controller、Service 和接口",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 8",
                        "default": 8
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file",
            "description": "读取特定文件的完整内容（基于路径关键词匹配）",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径关键词，如：ConflictModal、RescheduleArrangeForm"
                    },
                    "project_id": {
                        "type": "string",
                        "description": "项目ID（可选，留空则全局搜索）",
                        "default": ""
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]


class DesignToolExecutor:
    def __init__(self, frontend_project_ids: list[str], backend_project_ids: list[str]):
        self.frontend_ids = frontend_project_ids
        self.backend_ids = backend_project_ids
        self.all_ids = frontend_project_ids + backend_project_ids

    def execute(self, tool_name: str, arguments: dict) -> dict:
        if tool_name == "search_frontend":
            return self._search(arguments.get("query", ""), self.frontend_ids, arguments.get("top_k", 8))
        elif tool_name == "search_backend":
            return self._search(arguments.get("query", ""), self.backend_ids, arguments.get("top_k", 8))
        elif tool_name == "get_file":
            return self._get_file(arguments.get("file_path", ""), arguments.get("project_id", ""))
        else:
            return {"error": f"未知工具: {tool_name}"}

    def _search(self, query: str, project_ids: list[str], top_k: int) -> dict:
        results = {}
        for pid in project_ids:
            docs = retrieve_by_project(query, pid, top_k)
            if docs:
                results[pid] = [
                    {
                        "path": d["path"],
                        "content": d["content"][:1000],
                        "score": round(d["score"], 3),
                        "chunk_type": d.get("chunk_type", ""),
                        "functions": d.get("functions", ""),
                        "exports": d.get("exports", ""),
                    }
                    for d in docs
                ]
        return {
            "query": query,
            "results": results,
            "total": sum(len(v) for v in results.values()),
        }

    def _get_file(self, file_path: str, project_id: str) -> dict:
        search_ids = [project_id] if project_id else self.all_ids
        for pid in search_ids:
            docs = retrieve_by_path(pid, file_path, 15)
            if docs:
                return {
                    "project_id": pid,
                    "path": docs[0]["path"],
                    "chunks": [
                        {"content": d["content"], "chunk_type": d.get("chunk_type", "")}
                        for d in docs
                    ],
                }
        return {"error": f"未找到文件: {file_path}"}


class DesignAgent:
    def __init__(
        self,
        frontend_project_ids: list[str],
        backend_project_ids: list[str],
        max_rounds: int = 12,
    ):
        self.frontend_ids = frontend_project_ids
        self.backend_ids = backend_project_ids
        self.max_rounds = max_rounds
        self.tool_executor = DesignToolExecutor(frontend_project_ids, backend_project_ids)

    def _call_llm_with_tools(self, messages: list[dict]) -> dict:
        """调用 ZhipuAI（带工具定义），返回原始 message dict"""
        resp = httpx.post(
            f"{ZHIPU_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
            json={
                "model": ZHIPU_LLM_MODEL,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "stream": False,
                "temperature": 0.1,
            },
            timeout=httpx.Timeout(timeout=300.0),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]

    def _call_llm_plain(self, messages: list[dict]) -> str:
        """最后一轮：强制生成文档，不带工具"""
        if LLM_PROVIDER == "zhipu":
            resp = httpx.post(
                f"{ZHIPU_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
                json={"model": ZHIPU_LLM_MODEL, "messages": messages, "stream": False, "temperature": 0.1},
                timeout=httpx.Timeout(timeout=300.0),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        else:
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": LLM_MODEL, "messages": messages, "stream": False, "options": {"temperature": 0.1}},
                timeout=httpx.Timeout(timeout=300.0),
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    def run(self, requirement: str, doc_title: str = "") -> Generator[AgentStep, None, None]:
        title = doc_title or "需求分析"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"请分析以下产品需求，先调用工具搜索代码，再生成详细设计文档。\n\n需求标题：{title}\n\n需求内容：\n{requirement}",
            },
        ]

        all_sources = []
        tool_call_count = 0

        for round_num in range(1, self.max_rounds + 1):
            yield AgentStep(step_type="thinking", content=f"第 {round_num} 轮分析...", round=round_num)

            try:
                # 前 max_rounds-1 轮带工具，最后一轮强制生成
                if round_num < self.max_rounds:
                    msg = self._call_llm_with_tools(messages)
                else:
                    messages.append({
                        "role": "user",
                        "content": "你已收集足够的代码信息，请现在输出完整的详细设计文档。",
                    })
                    final = self._call_llm_plain(messages)
                    yield AgentStep(
                        step_type="final_answer",
                        content=final,
                        round=round_num,
                        metadata={"total_rounds": round_num, "sources": all_sources[:30]},
                    )
                    return
            except Exception as e:
                yield AgentStep(step_type="error", content=f"LLM 调用失败: {e}", round=round_num)
                return

            tool_calls = msg.get("tool_calls")

            if tool_calls:
                # 有工具调用 → 执行每个工具
                messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

                for tc in tool_calls:
                    fn = tc["function"]
                    tool_name = fn["name"]
                    try:
                        arguments = json.loads(fn["arguments"])
                    except Exception:
                        arguments = {}

                    tool_call_count += 1
                    yield AgentStep(
                        step_type="tool_call",
                        content=f"检索：{tool_name}({arguments.get('query', arguments.get('file_path', ''))})",
                        round=round_num,
                        metadata={"tool": tool_name, "arguments": arguments},
                    )

                    result = self.tool_executor.execute(tool_name, arguments)

                    # 收集来源
                    if "results" in result:
                        for pid, docs in result["results"].items():
                            for d in docs:
                                all_sources.append({"project_id": pid, "path": d["path"], "score": d["score"]})

                    found_count = result.get("total", len(result.get("chunks", [])))
                    yield AgentStep(
                        step_type="tool_result",
                        content=f"找到 {found_count} 个相关片段",
                        round=round_num,
                        metadata={"result_summary": f"{tool_name} 返回 {found_count} 结果"},
                    )

                    # 把工具结果加入对话
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False)[:4000],
                    })

            else:
                # 无工具调用 = LLM 决定直接输出文档
                content = msg.get("content", "")

                if tool_call_count == 0:
                    # 完全没有工具调用过，强制继续搜索
                    yield AgentStep(
                        step_type="thinking",
                        content="未调用工具，强制触发搜索...",
                        round=round_num,
                    )
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": "你还没有调用任何工具！请立即调用 search_frontend 和 search_backend 搜索相关代码，不要直接生成文档。",
                    })
                    continue

                unique_sources = list({f"{s['project_id']}:{s['path']}": s for s in all_sources}.values())
                yield AgentStep(
                    step_type="final_answer",
                    content=content,
                    round=round_num,
                    metadata={
                        "total_rounds": round_num,
                        "sources": unique_sources[:30],
                    },
                )
                return
