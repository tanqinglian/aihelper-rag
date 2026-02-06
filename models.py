"""数据模型定义"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class ProjectStatus(str, Enum):
    """项目状态"""
    IDLE = "idle"           # 未索引
    INDEXING = "indexing"   # 索引中
    INDEXED = "indexed"     # 已索引
    ERROR = "error"         # 索引失败


class PreprocessorConfig(BaseModel):
    """预处理配置"""
    remove_comments: bool = True
    remove_debug_statements: bool = True
    remove_eslint_comments: bool = True
    normalize_whitespace: bool = True

    chunk_strategy: str = "semantic"  # "semantic" | "none"
    chunk_max_chars: int = 1500
    chunk_min_chars: int = 200
    chunk_overlap_lines: int = 3

    max_chunk_chars: int = 2000
    extract_metadata: bool = True


class CodeChunk(BaseModel):
    """代码分块结果"""
    chunk_id: str               # "{file_path}#chunk_{index}"
    content: str                # 清洗后的代码
    chunk_type: str             # "imports" | "function" | "class" | "component" | "module_scope"
    start_line: int = 0
    end_line: int = 0

    file_path: str = ""
    module: str = ""
    sub_module: str = ""
    functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)

    embed_text: str = ""


class ProjectConfig(BaseModel):
    """项目配置"""
    extensions: list[str] = [".js", ".jsx", ".ts", ".tsx", ".less", ".css", ".vue"]
    ignore_dirs: list[str] = ["node_modules", ".umi", ".umi-production", "dist", ".git", "__pycache__"]
    max_file_chars: int = 6000
    preprocessor: PreprocessorConfig = Field(default_factory=PreprocessorConfig)


class Project(BaseModel):
    """项目模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    source_dir: str
    config: ProjectConfig = Field(default_factory=ProjectConfig)
    status: ProjectStatus = ProjectStatus.IDLE
    file_count: int = 0
    index_size_bytes: int = 0
    last_indexed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    error_message: Optional[str] = None


# API 请求/响应模型
class CreateProjectRequest(BaseModel):
    """创建项目请求"""
    name: str
    source_dir: str
    config: Optional[ProjectConfig] = None


class UpdateProjectRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    source_dir: Optional[str] = None
    config: Optional[ProjectConfig] = None


class AskRequest(BaseModel):
    """问答请求"""
    question: str
    project_id: str
    top_k: int = 3


class AskResponse(BaseModel):
    """问答响应"""
    answer: str
    sources: list[dict]


class IndexProgressEvent(BaseModel):
    """索引进度事件"""
    type: str  # scan_start, scan_complete, indexing, file_error, saving, complete, error
    data: dict


# ============ Agent 相关模型 ============

class AgentStep(BaseModel):
    """Agent 推理步骤"""
    step_type: str  # "thinking" | "tool_call" | "tool_result" | "final_answer"
    content: str
    round: int = 0
    metadata: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentAskRequest(BaseModel):
    """Agent 问答请求"""
    question: str
    project_ids: list[str]  # 支持多项目
    max_rounds: int = 5


class AgentAskResponse(BaseModel):
    """Agent 问答响应"""
    answer: str
    steps: list[dict] = []
    sources: list[dict] = []
    total_rounds: int = 0
