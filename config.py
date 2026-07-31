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

# ZhipuAI 配置（智谱 GLM）
# 生产环境建议通过环境变量 ZHIPU_API_KEY 注入，不要提交 Key 到 git
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "2b3a088b284348f88b30baa25f0b35eb.rGKCgdwwbpPBQEOP")
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_LLM_MODEL = "glm-5"   # 可选: glm-4-plus, glm-4-flash (快速免费), glm-z1-flash (带推理链)

# LLM 提供商切换: "ollama" | "zhipu"
LLM_PROVIDER = "zhipu"
