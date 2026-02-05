"""代码解析与索引模块 - LanceDB 版本"""
import os
import time
from typing import Generator
import httpx
import numpy as np
import lancedb
from config import OLLAMA_BASE_URL, EMBED_MODEL, LANCEDB_DIR
from preprocessor import preprocess_file
from models import PreprocessorConfig


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


def scan_files(
    source_dir: str,
    extensions: list[str],
    ignore_dirs: list[str],
    max_file_chars: int
) -> list[dict]:
    """扫描源码目录，返回文件信息列表"""
    files = []
    ignore_set = set(ignore_dirs)
    ext_set = set(extensions)

    for root, dirs, filenames in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in ignore_set]
        for fname in filenames:
            ext = os.path.splitext(fname)[1]
            if ext not in ext_set:
                continue
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, source_dir)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            if not content.strip():
                continue
            if len(content) > max_file_chars:
                content = content[:max_file_chars] + "\n// ... truncated"
            parts = rel_path.split(os.sep)
            module = parts[0] if parts else "root"
            sub_module = parts[1] if len(parts) > 1 else ""
            files.append({
                "path": rel_path,
                "module": module,
                "sub_module": sub_module,
                "content": content,
            })
    return files


def _save_to_lancedb(project_id: str, records: list[dict]):
    """将记录保存到 LanceDB"""
    db = get_lancedb()
    table_name = get_table_name(project_id)

    # 删除旧表（如果存在）
    try:
        db.drop_table(table_name)
    except Exception:
        pass

    # 创建新表
    db.create_table(table_name, records)


def index_project_stream(
    project_id: str,
    source_dir: str,
    extensions: list[str],
    ignore_dirs: list[str],
    max_file_chars: int,
    project_manager,
    preprocessor_config: PreprocessorConfig = None
) -> Generator[dict, None, None]:
    """
    流式索引项目，生成进度事件（LanceDB 版本，支持预处理）

    事件类型:
    - scan_start: 开始扫描
    - scan_complete: 扫描完成，返回文件数
    - preprocessing: 正在预处理
    - indexing: 正在索引，返回当前进度
    - file_error: 单个文件处理失败
    - saving: 正在保存
    - complete: 完成
    - error: 发生错误
    """
    start_time = time.time()

    if preprocessor_config is None:
        preprocessor_config = PreprocessorConfig()

    try:
        # 阶段1: 扫描文件
        yield {"type": "scan_start", "data": {"message": "正在扫描源码目录..."}}

        files = scan_files(source_dir, extensions, ignore_dirs, max_file_chars)
        total_files = len(files)

        if total_files == 0:
            yield {"type": "error", "data": {"message": "未找到任何匹配的文件"}}
            return

        yield {"type": "scan_complete", "data": {"total_files": total_files}}

        # 阶段2: 预处理文件为 chunks
        yield {"type": "preprocessing", "data": {"message": "正在预处理代码..."}}

        all_chunks = []
        for f in files:
            try:
                chunks = preprocess_file(f, preprocessor_config)
                all_chunks.extend(chunks)
            except Exception as e:
                yield {
                    "type": "file_error",
                    "data": {"file": f["path"], "error": f"预处理失败: {str(e)}"}
                }

        total_chunks = len(all_chunks)
        yield {"type": "preprocessing_complete", "data": {
            "total_files": total_files,
            "total_chunks": total_chunks
        }}

        # 阶段3: 向量化
        records = []
        indexed_count = 0

        for i, chunk in enumerate(all_chunks):
            current = i + 1
            percent = round(current / total_chunks * 100, 1)
            elapsed = time.time() - start_time

            if i > 0:
                avg_time_per_chunk = elapsed / i
                remaining = avg_time_per_chunk * (total_chunks - i)
            else:
                remaining = 0

            yield {
                "type": "indexing",
                "data": {
                    "current_file": chunk.file_path,
                    "current_chunk": chunk.chunk_id,
                    "current": current,
                    "total": total_chunks,
                    "percent": percent,
                    "estimated_remaining_seconds": round(remaining)
                }
            }

            try:
                emb = get_embedding(chunk.embed_text)
                records.append({
                    "vector": np.array(emb, dtype=np.float32),
                    "path": chunk.file_path,
                    "module": chunk.module,
                    "sub_module": chunk.sub_module,
                    "content": chunk.content,
                    "chunk_id": chunk.chunk_id,
                    "chunk_type": chunk.chunk_type,
                    "functions": ",".join(chunk.functions),
                    "classes": ",".join(chunk.classes),
                    "exports": ",".join(chunk.exports),
                    "imports": ",".join(chunk.imports),
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                })
                indexed_count += 1
            except Exception as e:
                yield {
                    "type": "file_error",
                    "data": {"file": chunk.chunk_id, "error": str(e)}
                }

        # 阶段4: 保存到 LanceDB
        yield {"type": "saving", "data": {"message": "正在保存索引..."}}

        if records:
            _save_to_lancedb(project_id, records)

        # 更新项目状态
        project_manager.update_project(
            project_id,
            file_count=indexed_count,
            indexed_at=time.strftime("%Y-%m-%dT%H:%M:%S")
        )

        duration = round(time.time() - start_time, 1)

        yield {
            "type": "complete",
            "data": {
                "file_count": total_files,
                "chunk_count": indexed_count,
                "duration_seconds": duration
            }
        }

    except Exception as e:
        yield {"type": "error", "data": {"message": str(e)}}


def build_index_for_project(
    project_id: str,
    source_dir: str,
    extensions: list[str],
    ignore_dirs: list[str],
    max_file_chars: int,
    project_manager,
    preprocessor_config: PreprocessorConfig = None
) -> dict:
    """非流式索引项目，返回结果（LanceDB 版本，支持预处理）"""
    if preprocessor_config is None:
        preprocessor_config = PreprocessorConfig()

    files = scan_files(source_dir, extensions, ignore_dirs, max_file_chars)

    # 预处理文件为 chunks
    all_chunks = []
    for f in files:
        try:
            chunks = preprocess_file(f, preprocessor_config)
            all_chunks.extend(chunks)
        except Exception:
            continue

    records = []
    for chunk in all_chunks:
        try:
            emb = get_embedding(chunk.embed_text)
            records.append({
                "vector": np.array(emb, dtype=np.float32),
                "path": chunk.file_path,
                "module": chunk.module,
                "sub_module": chunk.sub_module,
                "content": chunk.content,
                "chunk_id": chunk.chunk_id,
                "chunk_type": chunk.chunk_type,
                "functions": ",".join(chunk.functions),
                "classes": ",".join(chunk.classes),
                "exports": ",".join(chunk.exports),
                "imports": ",".join(chunk.imports),
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            })
        except Exception:
            continue

    if records:
        _save_to_lancedb(project_id, records)

    project_manager.update_project(
        project_id,
        file_count=len(records),
        indexed_at=time.strftime("%Y-%m-%dT%H:%M:%S")
    )

    return {"file_count": len(files), "chunk_count": len(records)}


def delete_project_index(project_id: str) -> bool:
    """删除项目的 LanceDB 表"""
    try:
        db = get_lancedb()
        table_name = get_table_name(project_id)
        db.drop_table(table_name)
        return True
    except Exception:
        return False


# 保留旧的 build_index 函数用于 CLI
def build_index():
    """构建向量索引（兼容旧版CLI）"""
    from config import SOURCE_DIR, CODE_EXTENSIONS, IGNORE_DIRS, MAX_FILE_CHARS

    print(f"[1/3] 扫描源码目录: {SOURCE_DIR}")
    files = scan_files(SOURCE_DIR, list(CODE_EXTENSIONS), list(IGNORE_DIRS), MAX_FILE_CHARS)
    print(f"  -> 找到 {len(files)} 个文件")

    print(f"[2/3] 初始化 LanceDB: {LANCEDB_DIR}")
    os.makedirs(LANCEDB_DIR, exist_ok=True)

    print(f"[3/3] 向量化 (共 {len(files)} 个文件)...")
    records = []
    for i, f in enumerate(files):
        embed_text = f"文件路径: {f['path']}\n模块: {f['module']}\n\n{f['content']}"
        try:
            emb = get_embedding(embed_text)
        except Exception as e:
            print(f"  [跳过] {f['path']}: {e}")
            continue

        records.append({
            "vector": np.array(emb, dtype=np.float32),
            "path": f["path"],
            "module": f["module"],
            "sub_module": f["sub_module"],
            "content": f["content"],
        })

        if (i + 1) % 10 == 0 or i == len(files) - 1:
            print(f"  进度: {i + 1}/{len(files)}")

    if records:
        _save_to_lancedb("default", records)

    print(f"\n索引构建完成! 共索引 {len(records)} 个文件, 存储于 {LANCEDB_DIR}")
    return len(records)


if __name__ == "__main__":
    start = time.time()
    build_index()
    print(f"耗时: {time.time() - start:.1f}s")
