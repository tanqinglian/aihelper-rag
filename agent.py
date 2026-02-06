"""
Agent 模块 - 多轮推理与工具调用

支持:
- 跨多项目检索
- API 调用链追踪
- 自主推理循环
"""
import json
import re
from typing import Generator, Optional
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from config import OLLAMA_BASE_URL, LLM_MODEL
from retriever import retrieve_by_project, retrieve_multi_project, retrieve_by_path, get_all_project_ids
from models import AgentStep


# 工具定义 (用于 LLM 理解)
TOOL_DEFINITIONS = [
    {
        "name": "multi_search",
        "description": "在多个项目中搜索代码。用于查找相关代码，支持跨前端、后端项目搜索。",
        "parameters": {
            "query": "搜索查询词 - 描述你要找的代码功能",
            "project_ids": "项目 ID 列表，可选，默认搜索所有项目",
            "top_k": "每个项目返回的结果数，默认 3"
        }
    },
    {
        "name": "trace_api",
        "description": "追踪 API 调用链。从前端 API 调用追踪到后端处理函数。",
        "parameters": {
            "api_path": "API 路径，如 '/api/users' 或 'getUserList'",
            "project_ids": "要追踪的项目 ID 列表"
        }
    },
    {
        "name": "get_file",
        "description": "获取指定文件的完整代码。用于查看文件详细实现。",
        "parameters": {
            "file_path": "文件路径，如 'pages/Order/index.jsx'",
            "project_id": "项目 ID"
        }
    },
    {
        "name": "search_function",
        "description": "按函数/组件名搜索。精确查找特定函数或组件的定义。",
        "parameters": {
            "name": "函数或组件名称",
            "project_ids": "项目 ID 列表"
        }
    }
]


def _build_tools_description() -> str:
    """构建工具描述文本"""
    lines = []
    for t in TOOL_DEFINITIONS:
        params_str = ", ".join([f"{k}: {v}" for k, v in t["parameters"].items()])
        lines.append(f"- **{t['name']}**: {t['description']}\n  参数: {params_str}")
    return "\n".join(lines)


class AgentToolExecutor:
    """工具执行器"""

    def __init__(self, available_project_ids: list[str]):
        self.available_project_ids = available_project_ids

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """执行工具并返回结果"""
        if tool_name == "multi_search":
            return self._multi_search(
                query=arguments.get("query", ""),
                project_ids=arguments.get("project_ids", self.available_project_ids),
                top_k=arguments.get("top_k", 3)
            )
        elif tool_name == "trace_api":
            return self._trace_api(
                api_path=arguments.get("api_path", ""),
                project_ids=arguments.get("project_ids", self.available_project_ids)
            )
        elif tool_name == "get_file":
            return self._get_file(
                file_path=arguments.get("file_path", ""),
                project_id=arguments.get("project_id", "")
            )
        elif tool_name == "search_function":
            return self._search_function(
                name=arguments.get("name", ""),
                project_ids=arguments.get("project_ids", self.available_project_ids)
            )
        else:
            return {"error": f"未知工具: {tool_name}"}

    def _multi_search(self, query: str, project_ids: list[str], top_k: int = 3) -> dict:
        """跨项目搜索"""
        if not project_ids or project_ids == ["all"]:
            project_ids = self.available_project_ids

        results = {}
        for pid in project_ids:
            if pid in self.available_project_ids:
                docs = retrieve_by_project(query, pid, top_k)
                results[pid] = [
                    {
                        "path": d["path"],
                        "content": d["content"][:800],  # 截断
                        "score": round(d["score"], 3),
                        "chunk_type": d.get("chunk_type", ""),
                        "functions": d.get("functions", ""),
                        "exports": d.get("exports", ""),
                    }
                    for d in docs
                ]

        return {
            "query": query,
            "projects_searched": list(results.keys()),
            "results": results,
            "total_results": sum(len(r) for r in results.values())
        }

    def _trace_api(self, api_path: str, project_ids: list[str]) -> dict:
        """API 调用链追踪"""
        if not project_ids:
            project_ids = self.available_project_ids

        traces = {
            "frontend_calls": [],
            "backend_handlers": [],
            "services": []
        }

        # 不同层级的搜索关键词
        search_patterns = [
            # 前端 API 调用
            (f"fetch {api_path}", "frontend_calls"),
            (f"axios {api_path}", "frontend_calls"),
            (f"request {api_path}", "frontend_calls"),
            (f"api {api_path}", "frontend_calls"),
            # 后端路由
            (f"router {api_path}", "backend_handlers"),
            (f"@GetMapping {api_path}", "backend_handlers"),
            (f"@PostMapping {api_path}", "backend_handlers"),
            (f"app.get {api_path}", "backend_handlers"),
            (f"app.post {api_path}", "backend_handlers"),
            # 通用搜索
            (api_path, "backend_handlers"),
        ]

        seen_paths = set()

        for query, category in search_patterns[:6]:  # 限制搜索次数
            for pid in project_ids:
                docs = retrieve_by_project(query, pid, 2)
                for d in docs:
                    if d["path"] in seen_paths:
                        continue
                    seen_paths.add(d["path"])

                    item = {
                        "project_id": pid,
                        "path": d["path"],
                        "content": d["content"][:500],
                        "functions": d.get("functions", ""),
                        "score": round(d["score"], 3)
                    }

                    # 根据路径特征分类
                    path_lower = d["path"].lower()
                    if any(p in path_lower for p in ["api/", "service", "request", "hook"]):
                        traces["frontend_calls"].append(item)
                    elif any(p in path_lower for p in ["controller", "router", "handler", "route", "api"]):
                        traces["backend_handlers"].append(item)
                    elif any(p in path_lower for p in ["service", "dao", "repository", "model"]):
                        traces["services"].append(item)
                    else:
                        traces[category].append(item)

        return {
            "api_path": api_path,
            "traces": traces,
            "summary": f"找到 {len(traces['frontend_calls'])} 个前端调用, "
                      f"{len(traces['backend_handlers'])} 个后端处理, "
                      f"{len(traces['services'])} 个服务层"
        }

    def _get_file(self, file_path: str, project_id: str) -> dict:
        """获取文件详情"""
        if not project_id:
            # 尝试在所有项目中查找
            for pid in self.available_project_ids:
                docs = retrieve_by_path(pid, file_path, 5)
                if docs:
                    project_id = pid
                    break

        if not project_id:
            return {"error": f"未找到文件: {file_path}"}

        docs = retrieve_by_path(project_id, file_path, 5)

        if not docs:
            return {"error": f"未找到文件: {file_path}"}

        # 合并同一文件的所有 chunks
        file_content = []
        for d in docs:
            if file_path in d["path"]:
                file_content.append({
                    "chunk_id": d.get("chunk_id", ""),
                    "content": d["content"],
                    "chunk_type": d.get("chunk_type", ""),
                    "functions": d.get("functions", ""),
                    "start_line": d.get("start_line", 0),
                    "end_line": d.get("end_line", 0),
                })

        if not file_content:
            return {"error": f"未找到文件: {file_path}"}

        return {
            "project_id": project_id,
            "path": docs[0]["path"],
            "chunks": file_content,
            "total_chunks": len(file_content)
        }

    def _search_function(self, name: str, project_ids: list[str]) -> dict:
        """按函数名搜索"""
        if not project_ids:
            project_ids = self.available_project_ids

        results = {}
        query = f"function {name} export {name} const {name}"

        for pid in project_ids:
            docs = retrieve_by_project(query, pid, 5)
            # 过滤精确匹配
            matched = [
                {
                    "path": d["path"],
                    "content": d["content"][:600],
                    "functions": d.get("functions", ""),
                    "exports": d.get("exports", ""),
                    "score": round(d["score"], 3)
                }
                for d in docs
                if name.lower() in (d.get("functions", "") + d.get("exports", "")).lower()
            ]
            if matched:
                results[pid] = matched

        return {
            "name": name,
            "results": results,
            "total_matches": sum(len(r) for r in results.values())
        }


class CodeAgent:
    """
    代码分析 Agent - 多轮推理与工具调用

    使用 prompt-based tool calling (更稳定)
    """

    def __init__(
        self,
        project_ids: list[str],
        max_rounds: int = 5
    ):
        self.project_ids = project_ids
        self.max_rounds = max_rounds
        self.tool_executor = AgentToolExecutor(project_ids)

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        tools_desc = _build_tools_description()

        return f"""你是一个代码分析助手，可以搜索和分析多个项目的代码。

## 可用工具
{tools_desc}

## 工具调用格式
当你需要搜索或分析代码时，请输出以下 JSON 格式（必须是有效的 JSON）：
```json
{{"tool": "工具名", "arguments": {{"参数名": "参数值"}}}}
```

## 工作流程
1. 分析用户问题，确定需要搜索什么
2. 使用 multi_search 在相关项目中搜索代码
3. 根据搜索结果，决定是否需要更多信息：
   - 如果需要追踪 API 调用链，使用 trace_api
   - 如果需要查看完整文件，使用 get_file
   - 如果需要找特定函数，使用 search_function
4. 收集足够信息后，给出完整的分析答案

## 回答要求
- 调用工具时，只输出 JSON，不要有其他文字
- 给出最终答案时，不要输出 JSON
- 答案中要引用具体的文件路径
- 如果涉及前后端，说明调用链路

## 可用项目
{', '.join(self.project_ids)}

现在开始分析用户的问题。"""

    def _parse_tool_call(self, content: str) -> Optional[tuple[str, dict]]:
        """从 LLM 输出中解析工具调用"""
        # 尝试提取 JSON
        patterns = [
            r'```json\s*(\{.*?\})\s*```',  # markdown code block
            r'```\s*(\{.*?\})\s*```',       # code block without language
            r'(\{[^{}]*"tool"[^{}]*\})',    # inline JSON
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    if "tool" in data and "arguments" in data:
                        return data["tool"], data["arguments"]
                    elif "tool" in data:
                        return data["tool"], data.get("args", data.get("params", {}))
                except json.JSONDecodeError:
                    continue

        return None

    def _call_llm(self, messages: list[dict]) -> str:
        """调用 Ollama LLM"""
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2}  # 低温度，更稳定的工具调用
            },
            timeout=httpx.Timeout(timeout=300.0)
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def run(self, question: str) -> Generator[AgentStep, None, None]:
        """
        运行 Agent 推理循环

        Yields:
            AgentStep 对象，包含每一步的信息
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": question}
        ]

        all_tool_results = []
        all_sources = []

        for round_num in range(1, self.max_rounds + 1):
            yield AgentStep(
                step_type="thinking",
                content=f"第 {round_num} 轮分析中...",
                round=round_num
            )

            # 调用 LLM
            try:
                response = self._call_llm(messages)
            except Exception as e:
                yield AgentStep(
                    step_type="error",
                    content=f"LLM 调用失败: {str(e)}",
                    round=round_num
                )
                return

            # 检查是否有工具调用
            tool_call = self._parse_tool_call(response)

            if tool_call:
                tool_name, arguments = tool_call

                yield AgentStep(
                    step_type="tool_call",
                    content=f"调用工具: {tool_name}",
                    round=round_num,
                    metadata={
                        "tool": tool_name,
                        "arguments": arguments
                    }
                )

                # 执行工具
                result = self.tool_executor.execute(tool_name, arguments)
                all_tool_results.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                })

                # 收集源文件
                sources = self._extract_sources(result)
                all_sources.extend(sources)

                yield AgentStep(
                    step_type="tool_result",
                    content=f"工具 {tool_name} 返回 {len(str(result))} 字符",
                    round=round_num,
                    metadata={"result": result, "sources": sources}
                )

                # 添加到对话历史
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"工具返回结果:\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)[:3000]}\n```\n\n请继续分析，或给出最终答案。"
                })

            else:
                # 没有工具调用 - 这是最终答案
                # 去重源文件
                unique_sources = []
                seen_paths = set()
                for s in all_sources:
                    key = f"{s.get('project_id', '')}:{s.get('path', '')}"
                    if key not in seen_paths:
                        seen_paths.add(key)
                        unique_sources.append(s)

                yield AgentStep(
                    step_type="final_answer",
                    content=response,
                    round=round_num,
                    metadata={
                        "total_rounds": round_num,
                        "tools_used": [r["tool"] for r in all_tool_results],
                        "sources": unique_sources[:20]  # 限制数量
                    }
                )
                return

        # 达到最大轮次
        yield AgentStep(
            step_type="final_answer",
            content=f"达到最大分析轮次 ({self.max_rounds})。基于已收集的信息，这是我的分析：\n\n" +
                    self._summarize_results(all_tool_results, question),
            round=self.max_rounds,
            metadata={
                "total_rounds": self.max_rounds,
                "max_rounds_reached": True,
                "sources": all_sources[:20]
            }
        )

    def _extract_sources(self, result: dict) -> list[dict]:
        """从工具结果中提取源文件"""
        sources = []

        # multi_search 结果
        if "results" in result and isinstance(result["results"], dict):
            for project_id, docs in result["results"].items():
                for d in docs:
                    sources.append({
                        "project_id": project_id,
                        "path": d.get("path", ""),
                        "score": d.get("score", 0)
                    })

        # trace_api 结果
        if "traces" in result:
            for category, items in result["traces"].items():
                for item in items:
                    sources.append({
                        "project_id": item.get("project_id", ""),
                        "path": item.get("path", ""),
                        "category": category
                    })

        # get_file 结果
        if "chunks" in result:
            sources.append({
                "project_id": result.get("project_id", ""),
                "path": result.get("path", "")
            })

        # search_function 结果
        if "results" in result and "name" in result:
            for project_id, docs in result["results"].items():
                for d in docs:
                    sources.append({
                        "project_id": project_id,
                        "path": d.get("path", "")
                    })

        return sources

    def _summarize_results(self, tool_results: list[dict], question: str) -> str:
        """汇总工具结果生成答案"""
        if not tool_results:
            return "未能找到相关代码信息。"

        summary_parts = []
        for tr in tool_results:
            tool = tr["tool"]
            result = tr["result"]

            if tool == "multi_search" and "results" in result:
                for pid, docs in result["results"].items():
                    for d in docs:
                        summary_parts.append(f"- {pid}: {d.get('path', '')}")

            elif tool == "trace_api" and "traces" in result:
                summary_parts.append(f"API 追踪: {result.get('summary', '')}")

        if summary_parts:
            return "找到以下相关代码:\n" + "\n".join(summary_parts[:15])
        return "未能找到相关代码信息。"


if __name__ == "__main__":
    # 测试
    project_ids = get_all_project_ids()
    print(f"可用项目: {project_ids}")

    if project_ids:
        agent = CodeAgent(project_ids, max_rounds=3)

        print("\n开始测试 Agent...\n")
        for step in agent.run("聊天页面是怎么实现的？"):
            print(f"[{step.step_type}] Round {step.round}: {step.content[:100]}...")
            if step.metadata:
                print(f"  Metadata: {list(step.metadata.keys())}")
