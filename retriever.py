"""检索模块 - LanceDB 版本"""
import os
import httpx
import numpy as np
import lancedb
from config import OLLAMA_BASE_URL, EMBED_MODEL, TOP_K, LANCEDB_DIR


def get_lancedb():
    """获取 LanceDB 连接"""
    os.makedirs(LANCEDB_DIR, exist_ok=True)
    return lancedb.connect(LANCEDB_DIR)


def get_table_name(project_id: str) -> str:
    """获取项目对应的表名"""
    safe_name = project_id.replace("-", "_").replace(".", "_")
    return f"project_{safe_name}"


def get_embedding(text: str) -> list[float]:
    """调用 Ollama 获取文本向量"""
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def retrieve_by_project(query: str, project_id: str, top_k: int = TOP_K) -> list[dict]:
    """按项目 ID 检索（LanceDB 版本）"""
    try:
        db = get_lancedb()
        table_name = get_table_name(project_id)
        table = db.open_table(table_name)
    except Exception:
        return []

    # 获取查询向量
    query_embedding = get_embedding(query)
    query_vector = np.array(query_embedding, dtype=np.float32)

    # 使用 LanceDB 向量搜索
    results = table.search(query_vector).limit(top_k).to_list()

    # 转换为原有格式
    items = []
    for r in results:
        # LanceDB 返回的 _distance 是 L2 距离，转换为相似度
        # 使用 1 / (1 + distance) 作为相似度分数
        distance = r.get("_distance", 0)
        score = 1 / (1 + distance)

        items.append({
            "path": r.get("path", ""),
            "module": r.get("module", ""),
            "content": r.get("content", ""),
            "score": score,
            "chunk_id": r.get("chunk_id", ""),
            "chunk_type": r.get("chunk_type", ""),
            "functions": r.get("functions", ""),
            "classes": r.get("classes", ""),
            "exports": r.get("exports", ""),
            "imports": r.get("imports", ""),
            "start_line": r.get("start_line", 0),
            "end_line": r.get("end_line", 0),
        })

    return items


# 兼容旧版调用
def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """检索（兼容旧版CLI，使用默认表）"""
    try:
        db = get_lancedb()
        table = db.open_table("project_default")
    except Exception:
        return []

    query_embedding = get_embedding(query)
    query_vector = np.array(query_embedding, dtype=np.float32)

    results = table.search(query_vector).limit(top_k).to_list()

    items = []
    for r in results:
        distance = r.get("_distance", 0)
        score = 1 / (1 + distance)

        items.append({
            "path": r.get("path", ""),
            "module": r.get("module", ""),
            "content": r.get("content", ""),
            "score": score,
        })

    return items


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "排课功能"
    results = retrieve(query)
    for r in results:
        print(f"[{r['score']:.4f}] {r['path']} ({r['module']})")
