from __future__ import annotations
"""
Central configuration module for the Deterministic Brain.

All values are read from environment variables with sensible defaults.
Import `cfg` anywhere to access configuration.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on actual env vars


@dataclass(frozen=True)
class BrainConfig:
    # --- Qdrant ---
    qdrant_url: str = field(default_factory=lambda: os.getenv('QDRANT_URL', ''))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv('QDRANT_API_KEY', ''))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv('RETRIEVAL_TOP_K', '5')))

    # --- Neo4j ---
    neo4j_uri: str = field(default_factory=lambda: os.getenv('NEO4J_URI', ''))
    neo4j_user: str = field(default_factory=lambda: os.getenv('NEO4J_USER', 'neo4j'))
    neo4j_password: str = field(default_factory=lambda: os.getenv('NEO4J_PASSWORD', ''))
    neo4j_depth: int = field(default_factory=lambda: int(os.getenv('NEO4J_DEPTH', '1')))

    # --- Tavily ---
    tavily_api_key: str = field(default_factory=lambda: os.getenv('TAVILY_API_KEY', ''))
    tavily_max_results: int = field(default_factory=lambda: int(os.getenv('TAVILY_MAX_RESULTS', '3')))

    # --- LLM (Qwen/llama.cpp) ---
    qwen_model_path: str = field(default_factory=lambda: os.getenv('QWEN_MODEL_PATH', ''))
    llm_ctx_size: int = field(default_factory=lambda: int(os.getenv('LLM_CTX_SIZE', '4096')))
    llm_max_tokens: int = field(default_factory=lambda: int(os.getenv('LLM_MAX_TOKENS', '512')))
    llm_seed: int = field(default_factory=lambda: int(os.getenv('LLM_SEED', '42')))

    # --- Code executor ---
    executor_timeout: int = field(default_factory=lambda: int(os.getenv('EXECUTOR_TIMEOUT', '5')))
    executor_recursion: int = field(default_factory=lambda: int(os.getenv('EXECUTOR_RECURSION', '100')))

    # --- Tracing ---
    tracing_enabled: bool = field(default_factory=lambda: os.getenv('TRACING_ENABLED', 'true').lower() != 'false')
    checkpoint_dir: Path = field(default_factory=lambda: Path(os.getenv('CHECKPOINT_DIR', '.checkpoints')))

    # --- API ---
    api_host: str = field(default_factory=lambda: os.getenv('API_HOST', '0.0.0.0'))
    api_port: int = field(default_factory=lambda: int(os.getenv('API_PORT', '8000')))

    # --- MCTS ---
    mcts_simulations: int = field(default_factory=lambda: int(os.getenv('MCTS_SIMULATIONS', '20')))
    mcts_branch_factor: int = field(default_factory=lambda: int(os.getenv('MCTS_BRANCH_FACTOR', '3')))
    mcts_max_depth: int = field(default_factory=lambda: int(os.getenv('MCTS_MAX_DEPTH', '4')))

    def summary(self) -> dict:
        """Return a non-sensitive summary for logging/debug."""
        return {
            'qdrant_url': self.qdrant_url or '(not set)',
            'neo4j_uri': self.neo4j_uri or '(not set)',
            'tavily_enabled': bool(self.tavily_api_key),
            'qwen_model': self.qwen_model_path or '(stub mode)',
            'tracing': self.tracing_enabled,
            'checkpoint_dir': str(self.checkpoint_dir),
            'api': f'{self.api_host}:{self.api_port}',
            'mcts_simulations': self.mcts_simulations,
        }


# Singleton
cfg = BrainConfig()
