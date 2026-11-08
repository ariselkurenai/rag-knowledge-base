"""全局配置：从项目根目录 .env 读取，代码中不再硬编码密钥"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── LLM（DeepSeek）──
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    chat_model: str = "deepseek-v4-flash"
    temperature: float = 0.1

    # ── Embedding（阿里百炼 DashScope，OpenAI 兼容模式）──
    dashscope_api_key: str = ""
    dashscope_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embed_model: str = "text-embedding-v4"

    # ── Rerank（DashScope 原生接口）──
    rerank_api_base: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )
    rerank_model: str = "gte-rerank"

    # ── 存储路径 ──
    persist_dir: Path = BASE_DIR / "chroma_db"
    data_dir: Path = BASE_DIR / "data"
    cache_dir: Path = BASE_DIR / "cache"
    results_dir: Path = BASE_DIR / "results"
    collection_name: str = "sizheng_cases"

    # ── MySQL（用户/专题/案例元数据/答疑记录/纠错留痕）──
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "sizheng_rag"

    # ── JWT 认证 ──
    jwt_secret: str = "change-me"
    jwt_expire_hours: int = 48

    # ── 切片参数 ──
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_chunk_size: int = 100  # 小于该长度的碎片向相邻块合并

    # ── 检索参数 ──
    retrieval_mode: str = "hybrid"  # dense | bm25 | hybrid
    k_dense: int = 10               # 向量检索候选数
    k_sparse: int = 10              # BM25 检索候选数
    k_final: int = 4                # 最终送入 LLM 的上下文数
    rrf_k: int = 60                 # RRF 融合常数
    use_rerank: bool = True
    rerank_candidates: int = 20     # 送入重排序的候选数

    # ── 对话与查询改写 ──
    max_history_turns: int = 5
    enable_query_rewrite: bool = True

    @property
    def mysql_url(self) -> str:
        return (f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
                f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
                "?charset=utf8mb4")

    @property
    def bm25_index(self) -> Path:
        return self.data_dir / f"bm25_{self.collection_name}.pkl"

    @property
    def eval_dir(self) -> Path:
        return self.data_dir / "eval"

    def ensure_dirs(self) -> None:
        for p in (self.persist_dir, self.data_dir, self.cache_dir,
                  self.results_dir, self.eval_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
