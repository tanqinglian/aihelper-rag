"""FastAPI 服务"""
import os
import json
import uuid
import httpx
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from config import OLLAMA_BASE_URL, EMBED_MODEL, LLM_MODEL, RERANK_ENABLED, RERANK_TOP_N, RERANK_VECTOR_WEIGHT, RERANK_BM25_WEIGHT
from models import (
    Project, ProjectConfig, ProjectStatus,
    CreateProjectRequest, UpdateProjectRequest,
    AskRequest, AskResponse, AgentAskRequest
)
from project_manager import project_manager
from retriever import retrieve_by_project
from reranker import rerank_documents
from generator import generate_with_docs, generate_stream_with_docs
from indexer import index_project_stream
from feishu_client import fetch_feishu_doc

app = FastAPI(title="Code RAG", description="代码知识库问答系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 健康检查 ============

@app.get("/health")
def health():
    return {"status": "ok"}


# ============ 项目管理 ============

@app.get("/projects")
def list_projects():
    """获取所有项目"""
    projects = project_manager.list_projects()
    return {"projects": [p.model_dump() for p in projects]}


@app.post("/projects")
def create_project(req: CreateProjectRequest):
    """创建新项目"""
    # 验证目录是否存在
    if not os.path.isdir(req.source_dir):
        raise HTTPException(400, f"目录不存在: {req.source_dir}")

    project = project_manager.create_project(
        name=req.name,
        source_dir=req.source_dir,
        config=req.config
    )
    return project.model_dump()


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    """获取项目详情"""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project.model_dump()


@app.put("/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest):
    """更新项目"""
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.source_dir is not None:
        if not os.path.isdir(req.source_dir):
            raise HTTPException(400, f"目录不存在: {req.source_dir}")
        updates["source_dir"] = req.source_dir
    if req.config is not None:
        updates["config"] = req.config

    project = project_manager.update_project(project_id, **updates)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project.model_dump()


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """删除项目"""
    success = project_manager.delete_project(project_id)
    if not success:
        raise HTTPException(404, "项目不存在")
    return {"message": "项目已删除"}


# ============ 索引管理 ============

@app.post("/projects/{project_id}/index")
def index_project(project_id: str):
    """开始索引项目（SSE 流式进度）"""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    # 更新状态为索引中
    project_manager.set_project_status(project_id, ProjectStatus.INDEXING)

    def event_generator():
        final_result = None
        has_error = False

        for event in index_project_stream(
            project_id=project_id,
            source_dir=project.source_dir,
            extensions=project.config.extensions,
            ignore_dirs=project.config.ignore_dirs,
            max_file_chars=project.config.max_file_chars,
            project_manager=project_manager,
            preprocessor_config=project.config.preprocessor
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if event["type"] == "complete":
                final_result = event["data"]
            elif event["type"] == "error":
                has_error = True

        # 更新项目状态
        if final_result:
            project_manager.set_project_status(
                project_id,
                ProjectStatus.INDEXED,
                file_count=final_result.get("chunk_count", final_result.get("file_count", 0)),
                last_indexed_at=datetime.now(),
                error_message=None
            )
        elif has_error:
            project_manager.set_project_status(
                project_id,
                ProjectStatus.ERROR
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ 问答接口 ============

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """问答接口（非流式）"""
    project = project_manager.get_project(req.project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if project.status != ProjectStatus.INDEXED:
        raise HTTPException(400, "项目未索引，请先进行索引")

    docs = retrieve_by_project(req.question, req.project_id, req.top_k)
    if not docs:
        raise HTTPException(400, "未找到相关文档")

    # Rerank 重排序
    if RERANK_ENABLED and len(docs) > RERANK_TOP_N:
        docs = rerank_documents(
            req.question, docs,
            top_n=RERANK_TOP_N,
            vector_weight=RERANK_VECTOR_WEIGHT,
            bm25_weight=RERANK_BM25_WEIGHT,
        )

    answer = generate_with_docs(req.question, docs)
    sources = [{
        "path": d["path"],
        "module": d["module"],
        "score": d["score"],
        "chunk_type": d.get("chunk_type", ""),
        "functions": d.get("functions", ""),
        "exports": d.get("exports", ""),
    } for d in docs]
    return AskResponse(answer=answer, sources=sources)


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """流式问答接口"""
    project = project_manager.get_project(req.project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if project.status != ProjectStatus.INDEXED:
        raise HTTPException(400, "项目未索引，请先进行索引")

    docs = retrieve_by_project(req.question, req.project_id, req.top_k)

    # Rerank 重排序
    if RERANK_ENABLED and len(docs) > RERANK_TOP_N:
        docs = rerank_documents(
            req.question, docs,
            top_n=RERANK_TOP_N,
            vector_weight=RERANK_VECTOR_WEIGHT,
            bm25_weight=RERANK_BM25_WEIGHT,
        )

    sources = [{
        "path": d["path"],
        "module": d["module"],
        "score": d["score"],
        "chunk_type": d.get("chunk_type", ""),
        "functions": d.get("functions", ""),
        "exports": d.get("exports", ""),
    } for d in docs]

    def event_generator():
        # 先发送sources
        yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
        # 流式发送内容
        for chunk in generate_stream_with_docs(req.question, docs):
            yield f"data: {json.dumps({'type': 'content', 'data': chunk}, ensure_ascii=False)}\n\n"
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ Agent 多轮推理接口 ============

@app.post("/ask/agent")
def ask_agent(req: AgentAskRequest):
    """Agent 多轮推理（SSE 流式返回推理过程）"""
    from agent import CodeAgent

    # 验证项目
    valid_project_ids = []
    for pid in req.project_ids:
        project = project_manager.get_project(pid)
        if project and project.status == ProjectStatus.INDEXED:
            valid_project_ids.append(pid)

    if not valid_project_ids:
        raise HTTPException(400, "没有可用的已索引项目")

    agent = CodeAgent(
        project_ids=valid_project_ids,
        max_rounds=min(req.max_rounds, 8)  # 硬上限 8 轮
    )

    def event_generator():
        steps = []
        final_answer = ""
        sources = []

        for step in agent.run(req.question):
            step_data = {
                "step_type": step.step_type,
                "content": step.content,
                "round": step.round,
                "metadata": step.metadata
            }
            steps.append(step_data)

            yield f"data: {json.dumps({'type': 'step', 'data': step_data}, ensure_ascii=False)}\n\n"

            if step.step_type == "final_answer":
                final_answer = step.content
                sources = step.metadata.get("sources", []) if step.metadata else []

        yield f"data: {json.dumps({'type': 'complete', 'data': {'answer': final_answer, 'sources': sources, 'total_steps': len(steps)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/projects/indexed")
def list_indexed_projects():
    """获取已索引项目列表"""
    projects = project_manager.list_projects()
    indexed = [p for p in projects if p.status == ProjectStatus.INDEXED]
    return {
        "projects": [
            {"id": p.id, "name": p.name, "file_count": p.file_count}
            for p in indexed
        ]
    }


# ============ 监控接口 ============

@app.get("/monitoring/ollama")
def check_ollama():
    """检查 Ollama 服务状态"""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])

        model_names = [m["name"] for m in models]

        return {
            "running": True,
            "base_url": OLLAMA_BASE_URL,
            "models": models,
            "embed_model_available": EMBED_MODEL in model_names or f"{EMBED_MODEL}:latest" in model_names,
            "llm_model_available": LLM_MODEL in model_names or f"{LLM_MODEL}:latest" in model_names,
            "required_embed_model": EMBED_MODEL,
            "required_llm_model": LLM_MODEL,
        }
    except Exception as e:
        return {
            "running": False,
            "base_url": OLLAMA_BASE_URL,
            "error": str(e),
            "embed_model_available": False,
            "llm_model_available": False,
            "required_embed_model": EMBED_MODEL,
            "required_llm_model": LLM_MODEL,
        }


@app.get("/monitoring/stats")
def get_stats():
    """获取系统统计信息"""
    projects = project_manager.list_projects()

    total_files = sum(p.file_count for p in projects)
    total_size = sum(p.index_size_bytes for p in projects)
    indexed_count = sum(1 for p in projects if p.status == ProjectStatus.INDEXED)

    return {
        "total_projects": len(projects),
        "indexed_projects": indexed_count,
        "total_indexed_files": total_files,
        "total_index_size_bytes": total_size,
        "projects_summary": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "file_count": p.file_count,
            }
            for p in projects
        ]
    }


@app.get("/monitoring/lancedb")
def get_lancedb_stats():
    """获取 LanceDB 向量数据库统计信息"""
    import lancedb
    from config import LANCEDB_DIR

    if not os.path.exists(LANCEDB_DIR):
        return {"tables": [], "total_size_bytes": 0}

    db = lancedb.connect(LANCEDB_DIR)
    tables_info = []

    total_size = 0
    for name in db.table_names():
        table = db.open_table(name)
        count = table.count_rows()
        schema = table.schema

        # 磁盘大小
        table_dir = os.path.join(LANCEDB_DIR, f'{name}.lance')
        table_size = 0
        if os.path.exists(table_dir):
            for root, dirs, files in os.walk(table_dir):
                for f in files:
                    table_size += os.path.getsize(os.path.join(root, f))
        total_size += table_size

        # 向量维度
        vector_dim = 0
        for field in schema:
            if field.name == 'vector':
                vector_dim = field.type.list_size
                break

        # 用 arrow 分析详细统计
        arrow_table = table.to_arrow()

        # 唯一文件数
        paths = arrow_table.column('path').to_pylist()
        unique_files = len(set(paths))

        # 内容长度
        contents = arrow_table.column('content').to_pylist()
        content_lens = [len(c) for c in contents]
        total_text_size = sum(content_lens)

        # chunk_type 分布
        chunk_types = {}
        if 'chunk_type' in [f.name for f in schema]:
            for ct in arrow_table.column('chunk_type').to_pylist():
                chunk_types[ct] = chunk_types.get(ct, 0) + 1

        # 模块分布
        modules = {}
        if 'module' in [f.name for f in schema]:
            for m in arrow_table.column('module').to_pylist():
                modules[m] = modules.get(m, 0) + 1

        # 元数据统计
        metadata_stats = {}
        for col in ['functions', 'exports', 'imports']:
            if col in [f.name for f in schema]:
                vals = arrow_table.column(col).to_pylist()
                non_empty = sum(1 for v in vals if v)
                metadata_stats[col] = {"total": count, "non_empty": non_empty}

        tables_info.append({
            "name": name,
            "chunk_count": count,
            "unique_files": unique_files,
            "avg_chunks_per_file": round(count / unique_files, 1) if unique_files > 0 else 0,
            "size_bytes": table_size,
            "vector_dim": vector_dim,
            "total_text_bytes": total_text_size,
            "content_stats": {
                "min_chars": min(content_lens) if content_lens else 0,
                "max_chars": max(content_lens) if content_lens else 0,
                "avg_chars": round(sum(content_lens) / len(content_lens)) if content_lens else 0,
            },
            "chunk_types": chunk_types,
            "modules_top10": dict(sorted(modules.items(), key=lambda x: -x[1])[:10]),
            "metadata_stats": metadata_stats,
        })

    return {
        "tables": tables_info,
        "total_size_bytes": total_size,
    }


# ============ 路径验证 ============

@app.get("/validate-path")
def validate_path(path: str):
    """验证路径是否有效"""
    exists = os.path.isdir(path)
    return {
        "path": path,
        "valid": exists,
        "message": "目录存在" if exists else "目录不存在"
    }


# ============ 详细设计接口 ============

DESIGNS_FILE = os.path.join(os.path.dirname(__file__), "data", "designs.json")


def _load_designs() -> list:
    if not os.path.exists(DESIGNS_FILE):
        return []
    with open(DESIGNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_design(record: dict):
    designs = _load_designs()
    designs.insert(0, record)
    designs = designs[:100]
    with open(DESIGNS_FILE, "w", encoding="utf-8") as f:
        json.dump(designs, f, ensure_ascii=False, indent=2)


class DesignRequest(BaseModel):
    feishu_url: Optional[str] = None
    requirement_text: Optional[str] = None  # 直接输入文本时使用


@app.get("/design/fetch-doc")
def fetch_doc(url: str):
    """从飞书文档 URL 获取内容"""
    try:
        doc = fetch_feishu_doc(url)
        return doc
    except Exception as e:
        raise HTTPException(400, f"获取飞书文档失败: {str(e)}")


@app.post("/design/generate")
def design_generate(req: DesignRequest):
    """生成详细设计文档（SSE 流式）"""
    from design_agent import DesignAgent

    # 获取需求内容
    if req.feishu_url:
        try:
            doc = fetch_feishu_doc(req.feishu_url)
            requirement = doc["content"]
            doc_title = doc["title"]
        except Exception as e:
            raise HTTPException(400, f"获取飞书文档失败: {str(e)}")
    elif req.requirement_text:
        requirement = req.requirement_text
        doc_title = ""
    else:
        raise HTTPException(400, "请提供 feishu_url 或 requirement_text")

    # 按 project_type 分类已索引的项目
    all_projects = project_manager.list_projects()
    indexed = [p for p in all_projects if p.status == ProjectStatus.INDEXED]
    frontend_ids = [p.id for p in indexed if p.config.project_type == "frontend"]
    backend_ids = [p.id for p in indexed if p.config.project_type == "backend"]

    if not frontend_ids and not backend_ids:
        raise HTTPException(400, "没有已索引的项目，请先在训练页面完成索引")

    agent = DesignAgent(frontend_ids, backend_ids, max_rounds=10)

    def event_generator():
        final_doc = ""
        for step in agent.run(requirement, doc_title):
            step_data = {
                "step_type": step.step_type,
                "content": step.content,
                "round": step.round,
                "metadata": step.metadata,
            }
            yield f"data: {json.dumps({'type': 'step', 'data': step_data}, ensure_ascii=False)}\n\n"

            if step.step_type == "final_answer":
                final_doc = step.content
                _save_design({
                    "id": str(uuid.uuid4())[:8],
                    "title": doc_title or "未命名需求",
                    "feishu_url": req.feishu_url or "",
                    "document": final_doc,
                    "created_at": datetime.now().isoformat(),
                })

        yield f"data: {json.dumps({'type': 'complete', 'data': {'document': final_doc}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/design/history")
def design_history():
    """获取设计文档历史列表"""
    designs = _load_designs()
    return [
        {"id": d["id"], "title": d["title"], "feishu_url": d.get("feishu_url", ""), "created_at": d["created_at"]}
        for d in designs
    ]


@app.get("/design/history/{design_id}")
def design_get(design_id: str):
    """获取单条设计文档"""
    for d in _load_designs():
        if d["id"] == design_id:
            return d
    raise HTTPException(404, "记录不存在")


@app.delete("/design/history/{design_id}")
def design_delete(design_id: str):
    """删除设计文档"""
    designs = [d for d in _load_designs() if d["id"] != design_id]
    with open(DESIGNS_FILE, "w", encoding="utf-8") as f:
        json.dump(designs, f, ensure_ascii=False, indent=2)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
