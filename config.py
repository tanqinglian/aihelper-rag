"""配置"""
import os

# Ollama 配置
OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "bge-m3"
LLM_MODEL = "qwen2.5-coder:14b"

# 项目源码路径（示例，通过 Web 界面配置具体项目）
# SOURCE_DIR = "/path/to/your/project/src"

# 代码文件后缀
CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".less"}

# 忽略目录
IGNORE_DIRS = {"node_modules", ".umi", ".umi-production", "dist", ".git"}

# 向量索引存储路径（旧版 JSON 方式，保留兼容）
INDEX_PATH = os.path.join(os.path.dirname(__file__), "data", "index.json")

# LanceDB 配置
LANCEDB_DIR = os.path.join(os.path.dirname(__file__), "data", "lancedb")

# 检索配置
TOP_K = 5

# Rerank 配置
RERANK_ENABLED = True
RERANK_TOP_N = 8          # Rerank 后保留的文档数
RERANK_VECTOR_WEIGHT = 0.4  # 向量相似度权重
RERANK_BM25_WEIGHT = 0.6    # BM25 关键词权重

# 单文件最大字符数（超过则截断）
MAX_FILE_CHARS = 6000

# 预处理配置默认值
DEFAULT_CHUNK_MAX_CHARS = 1500
DEFAULT_CHUNK_MIN_CHARS = 200
DEFAULT_CHUNK_OVERLAP_LINES = 3
DEFAULT_MAX_CHUNK_CHARS = 2000
