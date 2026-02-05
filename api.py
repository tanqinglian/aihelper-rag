"""FastAPI 服务"""
import os
import json
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
    AskRequest, AskResponse
)
from project_manager import project_manager
from retriever import retrieve_by_project
from reranker import rerank_documents
from generator import generate_with_docs, generate_stream_with_docs
from indexer import index_project_stream

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
