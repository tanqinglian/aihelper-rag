"""LLM 生成模块"""
import json
import httpx
from config import OLLAMA_BASE_URL, LLM_MODEL, LLM_PROVIDER, ZHIPU_API_KEY, ZHIPU_BASE_URL, ZHIPU_LLM_MODEL

SYSTEM_PROMPT = """你是一个代码知识库助手，负责回答代码相关问题。

请基于提供的代码片段准确回答问题。如果代码片段不足以回答，请明确说明。
回答时请引用具体的文件路径。"""


def _build_messages(question: str, docs: list[dict]):
    """构建LLM消息"""
    context_parts = []
    for i, doc in enumerate(docs, 1):
        content = doc['content'][:1500]

        # 构建增强的文件信息
        chunk_type = doc.get('chunk_type', '')
        chunk_info = f" ({chunk_type})" if chunk_type else ""

        functions = doc.get('functions', '')
        functions_info = f" [函数: {functions}]" if functions else ""

        exports = doc.get('exports', '')
        exports_info = f" [导出: {exports}]" if exports and not functions else ""

        context_parts.append(
            f"--- 文件 {i}: {doc['path']}{chunk_info}{functions_info}{exports_info} ---\n{content}"
        )
    context = "\n\n".join(context_parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"以下是检索到的相关代码:\n\n{context}\n\n---\n\n问题: {question}",
        },
    ]


def generate_with_docs(question: str, docs: list[dict]) -> str:
    """非流式生成回答"""
    messages = _build_messages(question, docs)
    if LLM_PROVIDER == "zhipu":
        return _zhipu_call(messages)
    return _ollama_call(messages)


def generate_stream_with_docs(question: str, docs: list[dict]):
    """流式生成回答，yield每个chunk"""
    messages = _build_messages(question, docs)
    if LLM_PROVIDER == "zhipu":
        yield from _zhipu_stream(messages)
    else:
        yield from _ollama_stream(messages)


def _zhipu_call(messages: list[dict]) -> str:
    """调用智谱 GLM（非流式）"""
    resp = httpx.post(
        f"{ZHIPU_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
        json={
            "model": ZHIPU_LLM_MODEL,
            "messages": messages,
            "stream": False,
        },
        timeout=httpx.Timeout(timeout=120.0),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _zhipu_stream(messages: list[dict]):
    """调用智谱 GLM（流式）"""
    with httpx.stream(
        "POST",
        f"{ZHIPU_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
        json={
            "model": ZHIPU_LLM_MODEL,
            "messages": messages,
            "stream": True,
        },
        timeout=httpx.Timeout(timeout=120.0, read=120.0),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    content = data["choices"][0]["delta"].get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


def _ollama_call(messages: list[dict]) -> str:
    """调用 Ollama LLM（非流式）"""
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": LLM_MODEL, "messages": messages, "stream": False},
        timeout=httpx.Timeout(timeout=600.0, read=600.0),
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _ollama_stream(messages: list[dict]):
    """调用 Ollama LLM（流式）"""
    with httpx.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": LLM_MODEL, "messages": messages, "stream": True},
        timeout=httpx.Timeout(timeout=600.0, read=600.0),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        content = data["message"]["content"]
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue


# 兼容旧版调用
def generate(question: str) -> str:
    """非流式生成回答（兼容旧版）"""
    from retriever import retrieve
    docs = retrieve(question, top_k=3)
    return generate_with_docs(question, docs)


def generate_stream(question: str):
    """流式生成回答（兼容旧版）"""
    from retriever import retrieve
    docs = retrieve(question, top_k=3)
    yield from generate_stream_with_docs(question, docs)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "排课功能是怎么实现的？"
    print(f"\n问题: {q}\n")
    print("检索中...")
    answer = generate(q)
    print(f"\n回答:\n{answer}")
