"""Config layer — BrainConfig + credential vault.

All values are read from environment variables (and .env via
pydantic-settings) with sensible defaults. Import `cfg` anywhere to access
configuration.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from config.credentials import CredentialVault, get_credential_vault
except ImportError:
    CredentialVault = None
    get_credential_vault = lambda: None

__all__ = [
    "BrainConfig",
    "cfg",
    "settings",
    "reload_config",
    "get_setting_schema",
    "persist_setting",
    "CredentialVault",
    "get_credential_vault",
]

_ENV_FILE = os.environ.get("DOTENV_PATH", ".env")


class BrainConfig(BaseSettings):
    """Fleet brain settings, loaded from environment / .env by pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Qdrant ---
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "brain_vectors"
    retrieval_top_k: int = 5

    # --- Gemma (local GGUF) ---
    gemma_base_url: str = "http://localhost:11434"

    # --- Unified local model service ---
    ollama_base_url: str = Field(
        "http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "GEMMA_BASE_URL"),
    )
    ollama_model: str = "qwen3:4b"
    local_model_fast: str = "qwen3:0.6b"
    llama_server_url: str = Field(
        "http://127.0.0.1:8082",
        validation_alias=AliasChoices("LLAMA_SERVER_URL", "LOCAL_MODEL_URL"),
    )
    local_model_name: str = ""

    # --- Neo4j ---
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_depth: int = 1

    # --- Tavily ---
    tavily_api_key: str = ""
    tavily_max_results: int = 3

    # --- OpenRouter ---
    openrouter_api_key: str = ""
    openrouter_site_url: str = "https://github.com/ncsound919/deterministic-brain"
    openrouter_site_name: str = "deterministic-brain"

    # --- opencode Go tier (funded LLM budget — LiteLLM gateway :4100) ---
    litellm_gateway_url: str = Field(
        "http://localhost:4100",
        validation_alias=AliasChoices("LITELLM_GATEWAY_URL", "LITELLM_URL"),
    )
    litellm_model: str = "opencode"
    opencode_go_url: str = "https://opencode.ai/zen/go/v1/chat/completions"
    opencode_go_model: str = "deepseek-v4-flash"

    # --- Research & Scientific ---
    alpha_genome_api_key: str = ""
    ncbi_api_key: str = ""
    xai_api_key: str = ""
    perplexity_api_key: str = ""

    # --- News ---
    newsapi_key: str = ""
    gnews_api_key: str = ""
    worldnews_api_key: str = ""

    # --- Content Creation ---
    elevenlabs_api_key: str = ""
    kling_api_key: str = ""
    whisper_api_key: str = ""

    # --- Per-lane model selection (OpenRouter fallback only — the brain's
    #     primary remote is the funded opencode Go tier, not these) ---
    model_coding: str = "openrouter/deepseek/deepseek-chat"
    model_business_logic: str = "openrouter/deepseek/deepseek-chat"
    model_agent_brain: str = "openrouter/deepseek/deepseek-chat"
    model_tool_calling: str = "openrouter/meta-llama/llama-3.3-70b-instruct"
    model_cross_domain: str = "openrouter/deepseek/deepseek-chat"
    model_default: str = "openrouter/deepseek/deepseek-chat"
    model_opencode: str = "openrouter/deepseek/deepseek-chat"

    # --- LLM general (llama.cpp fallback) ---
    qwen_model_path: str = ""
    llm_ctx_size: int = 4096
    llm_max_tokens: int = 2048
    llm_seed: int = 42

    # --- Code executor ---
    executor_timeout: int = 5
    executor_recursion: int = 100

    # --- Tracing ---
    tracing_enabled: bool = True
    checkpoint_dir: Path = Path(".checkpoints")

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- MCTS ---
    mcts_simulations: int = 20
    mcts_branch_factor: int = 3
    mcts_max_depth: int = 4

    # --- autoDream ---
    autodream_enabled: bool = True
    autodream_schedule: str = "0 3 * * *"
    trace_retention_days: int = 30

    # --- KAIROS ---
    kairos_enabled: bool = True
    kairos_idle_threshold_minutes: int = Field(
        5,
        validation_alias=AliasChoices("KAIROS_IDLE_THRESHOLD", "KAIROS_IDLE_THRESHOLD_MINUTES"),
    )
    kairos_dir: Path = Path(".kairos")

    def summary(self) -> dict:
        return {
            'qdrant_url':          self.qdrant_url or '(not set)',
            'neo4j_uri':           self.neo4j_uri or '(not set)',
            'tavily_enabled':      bool(self.tavily_api_key),
            'openrouter_enabled':  bool(self.openrouter_api_key),
            'gotier': {
                'gateway': self.litellm_gateway_url,
                'model': self.litellm_model,
                'direct_url': self.opencode_go_url,
                'direct_model': self.opencode_go_model,
                'enabled': bool(self.openrouter_api_key) or bool(self.litellm_gateway_url),
            },
            'models': {
                'coding':         self.model_coding,
                'business_logic': self.model_business_logic,
                'agent_brain':    self.model_agent_brain,
                'tool_calling':   self.model_tool_calling,
                'cross_domain':   self.model_cross_domain,
                'default':        self.model_default,
                'opencode':       self.model_opencode,
            },
            'local': {
                'ollama':  self.ollama_base_url,
                'ollama_model': self.ollama_model,
                'llama_server': self.llama_server_url,
                'preferred': self.local_model_name or '(auto)',
                'fast': self.local_model_fast,
            },
            'llm_fallback':        self.qwen_model_path or '(stub mode)',
            'tracing':             self.tracing_enabled,
            'checkpoint_dir':      str(self.checkpoint_dir),
            'api':                 f'{self.api_host}:{self.api_port}',
            'mcts_simulations':    self.mcts_simulations,
            'research': {
                'alpha_genome': bool(self.alpha_genome_api_key),
                'ncbi':         bool(self.ncbi_api_key),
                'xai':          bool(self.xai_api_key),
                'perplexity':   bool(self.perplexity_api_key),
            },
            'news_extensions': {
                'gnews':        bool(self.gnews_api_key),
                'worldnews':    bool(self.worldnews_api_key),
            }
        }

    def reload(self) -> None:
        """Re-read all fields from environment variables."""
        try:
            from dotenv import load_dotenv as _reload
            _reload(override=True)
        except ImportError:
            pass
        fresh = BrainConfig()
        for name in type(self).model_fields:
            setattr(self, name, getattr(fresh, name))


def reload_config() -> BrainConfig:
    """Re-read environment variables and return a fresh BrainConfig.

    NOTE: Does not override env vars already set in the process environment.
    Restart the process to pick up new .env file values.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return BrainConfig()


def get_setting_schema() -> dict:
    return {
        "Database": [
            {"key": "QDRANT_URL", "type": "string", "default": "", "label": "Qdrant URL"},
            {"key": "QDRANT_API_KEY", "type": "secret", "default": "", "label": "Qdrant API Key"},
            {"key": "RETRIEVAL_TOP_K", "type": "int", "default": "5", "label": "Retrieval Top-K", "min": 1, "max": 50},
            {"key": "NEO4J_URI", "type": "string", "default": "", "label": "Neo4j URI"},
            {"key": "NEO4J_USER", "type": "string", "default": "neo4j", "label": "Neo4j User"},
            {"key": "NEO4J_PASSWORD", "type": "secret", "default": "", "label": "Neo4j Password"},
            {"key": "NEO4J_DEPTH", "type": "int", "default": "1", "label": "Neo4j Depth", "min": 1, "max": 5},
        ],
        "Models": [
            {"key": "LOCAL_MODEL_NAME", "type": "string", "default": "", "label": "Preferred Local Model (leave blank for auto)"},
            {"key": "LOCAL_MODEL_FAST", "type": "string", "default": "qwen3:0.6b", "label": "Fast-tier Local Model (interactive calls)"},
            {"key": "OLLAMA_BASE_URL", "type": "string", "default": "http://localhost:11434", "label": "Ollama Base URL"},
            {"key": "OLLAMA_MODEL", "type": "string", "default": "qwen3:4b", "label": "Ollama Model"},
            {"key": "LLAMA_SERVER_URL", "type": "string", "default": "http://127.0.0.1:8082", "label": "llama-server URL"},
            {"key": "MODEL_CODING", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "Coding Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "MODEL_BUSINESS_LOGIC", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "Business Logic Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "MODEL_AGENT_BRAIN", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "Agent Brain Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "MODEL_TOOL_CALLING", "type": "select", "default": "openrouter/meta-llama/llama-3.3-70b-instruct", "label": "Tool Calling Model",
             "options": ["openrouter/meta-llama/llama-3.3-70b-instruct", "openrouter/deepseek/deepseek-chat"]},
            {"key": "MODEL_CROSS_DOMAIN", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "Cross-Domain Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "MODEL_DEFAULT", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "Default Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "MODEL_OPENCODE", "type": "select", "default": "openrouter/deepseek/deepseek-chat", "label": "OpenCode Model",
             "options": ["openrouter/deepseek/deepseek-chat", "openrouter/meta-llama/llama-3.3-70b-instruct"]},
            {"key": "LITELLM_GATEWAY_URL", "type": "string", "default": "http://localhost:4100", "label": "LiteLLM Gateway URL (funded Go tier)"},
            {"key": "LITELLM_MODEL", "type": "string", "default": "opencode", "label": "LiteLLM Gateway Model"},
            {"key": "OPENCODE_GO_URL", "type": "string", "default": "https://opencode.ai/zen/go/v1/chat/completions", "label": "Direct opencode Go tier URL"},
            {"key": "OPENCODE_GO_MODEL", "type": "string", "default": "deepseek-v4-flash", "label": "Direct opencode Go tier Model"},
            {"key": "LLM_CTX_SIZE", "type": "int", "default": "4096", "label": "LLM Context Size", "min": 1024, "max": 32768},
            {"key": "LLM_MAX_TOKENS", "type": "int", "default": "2048", "label": "LLM Max Tokens", "min": 256, "max": 16384},
            {"key": "LLM_SEED", "type": "int", "default": "42", "label": "LLM Seed", "min": 0, "max": 9999},
        ],
        "API": [
            {"key": "API_HOST", "type": "string", "default": "127.0.0.1", "label": "API Host"},
            {"key": "API_PORT", "type": "int", "default": "8000", "label": "API Port", "min": 1024, "max": 65535},
        ],
        "Voice": [
            {"key": "VOICE_MODEL_SIZE", "type": "select", "default": "tiny.en", "label": "STT Model Size"},
            {"key": "VOICE_TTS_VOICE", "type": "select", "default": "en_US-lessac-medium", "label": "TTS Voice"},
        ],
        "Daemons": [
            {"key": "TRACING_ENABLED", "type": "bool", "default": "true", "label": "Tracing Enabled"},
            {"key": "KAIROS_ENABLED", "type": "bool", "default": "true", "label": "KAIROS Enabled"},
            {"key": "KAIROS_IDLE_THRESHOLD", "type": "int", "default": "5", "label": "KAIROS Idle Threshold (min)", "min": 1, "max": 120},
            {"key": "AUTODREAM_ENABLED", "type": "bool", "default": "true", "label": "AutoDream Enabled"},
            {"key": "AUTODREAM_SCHEDULE", "type": "string", "default": "0 3 * * *", "label": "AutoDream Cron"},
            {"key": "TRACE_RETENTION_DAYS", "type": "int", "default": "30", "label": "Trace Retention (days)", "min": 1, "max": 365},
        ],
        "Healing": [
            {"key": "HEAL_ENABLED", "type": "bool", "default": "true", "label": "Self-Healing Enabled"},
            {"key": "HEAL_MAX_RETRIES", "type": "int", "default": "3", "label": "Max Heal Retries", "min": 1, "max": 10},
            {"key": "HEAL_CIRCUIT_BREAKER_THRESHOLD", "type": "int", "default": "5", "label": "Circuit Breaker Threshold", "min": 2, "max": 20},
        ],
        "MCTS": [
            {"key": "MCTS_SIMULATIONS", "type": "int", "default": "20", "label": "MCTS Simulations", "min": 1, "max": 200},
            {"key": "MCTS_BRANCH_FACTOR", "type": "int", "default": "3", "label": "MCTS Branch Factor", "min": 2, "max": 10},
            {"key": "MCTS_MAX_DEPTH", "type": "int", "default": "4", "label": "MCTS Max Depth", "min": 1, "max": 10},
        ],
    }


def persist_setting(key: str, value: str) -> bool:
    env_path = os.environ.get("DOTENV_PATH", ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
    key_upper = key.upper()
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key_upper}="):
            lines[i] = f"{key_upper}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"\n{key_upper}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    return True


cfg = BrainConfig()

# Alias for modules that import `settings`
settings = cfg
