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

    # cosine 距离范围 [0, 2]，0=完全相似 → score = 1 - distance/2，范围 [0, 1]
    results = table.search(query_vector).metric("cosine").limit(top_k).to_list()

    items = []
    for r in results:
        distance = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - distance / 2.0)

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


def retrieve_multi_project(
    query: str,
    project_ids: list[str],
    top_k: int = TOP_K
) -> dict[str, list[dict]]:
    """
    跨多项目检索

    Args:
        query: 查询文本
        project_ids: 项目 ID 列表
        top_k: 每个项目返回的结果数

    Returns:
        {project_id: [results]} 格式的字典
    """
    results = {}

    for project_id in project_ids:
        try:
            docs = retrieve_by_project(query, project_id, top_k)
            results[project_id] = docs
        except Exception:
            results[project_id] = []

    return results


def retrieve_by_path(
    project_id: str,
    file_path: str,
    top_k: int = 10
) -> list[dict]:
    """
    按文件路径检索（精确匹配）

    Args:
        project_id: 项目 ID
        file_path: 文件路径（支持部分匹配）
        top_k: 返回结果数

    Returns:
        匹配的文档列表
    """
    try:
        db = get_lancedb()
        table_name = get_table_name(project_id)
        table = db.open_table(table_name)
    except Exception:
        return []

    # 使用 SQL-like 过滤
    try:
        results = table.search().where(f"path LIKE '%{file_path}%'").limit(top_k).to_list()
    except Exception:
        return []

    items = []
    for r in results:
        items.append({
            "path": r.get("path", ""),
            "module": r.get("module", ""),
            "content": r.get("content", ""),
            "score": 1.0,
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


def get_all_project_ids() -> list[str]:
    """获取所有已索引的项目 ID"""
    try:
        db = get_lancedb()
        tables = db.table_names()
        # 从表名中提取项目 ID (格式: project_{id})
        project_ids = []
        for t in tables:
            if t.startswith("project_"):
                project_ids.append(t[8:])  # 移除 "project_" 前缀
        return project_ids
    except Exception:
        return []


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

    results = table.search(query_vector).metric("cosine").limit(top_k).to_list()

    items = []
    for r in results:
        distance = r.get("_distance", 1.0)
        score = max(0.0, 1.0 - distance / 2.0)

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
