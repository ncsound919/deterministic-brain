"""Config layer — BrainConfig + credential vault.

All values are read from environment variables with sensible defaults.
Import `cfg` anywhere to access configuration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from config.credentials import CredentialVault, get_credential_vault
except ImportError:
    CredentialVault = None
    get_credential_vault = lambda: None

__all__ = [
    "BrainConfig",
    "cfg",
    "reload_config",
    "get_setting_schema",
    "persist_setting",
    "CredentialVault",
    "get_credential_vault",
]


@dataclass(frozen=True)
class BrainConfig:
    # --- Qdrant ---
    qdrant_url:       str  = field(default_factory=lambda: os.getenv('QDRANT_URL', ''))
    qdrant_api_key:   str  = field(default_factory=lambda: os.getenv('QDRANT_API_KEY', ''))
    retrieval_top_k:  int  = field(default_factory=lambda: int(os.getenv('RETRIEVAL_TOP_K', '5')))

    # --- Neo4j ---
    neo4j_uri:        str  = field(default_factory=lambda: os.getenv('NEO4J_URI', ''))
    neo4j_user:       str  = field(default_factory=lambda: os.getenv('NEO4J_USER', 'neo4j'))
    neo4j_password:   str  = field(default_factory=lambda: os.getenv('NEO4J_PASSWORD', ''))
    neo4j_depth:      int  = field(default_factory=lambda: int(os.getenv('NEO4J_DEPTH', '1')))

    # --- Tavily ---
    tavily_api_key:      str = field(default_factory=lambda: os.getenv('TAVILY_API_KEY', ''))
    tavily_max_results:  int = field(default_factory=lambda: int(os.getenv('TAVILY_MAX_RESULTS', '3')))

    # --- OpenRouter ---
    openrouter_api_key:  str = field(default_factory=lambda: os.getenv('OPENROUTER_API_KEY', ''))
    openrouter_site_url: str = field(default_factory=lambda: os.getenv('OPENROUTER_SITE_URL', 'https://github.com/ncsound919/deterministic-brain'))
    openrouter_site_name:str = field(default_factory=lambda: os.getenv('OPENROUTER_SITE_NAME', 'deterministic-brain'))

    # --- Per-lane model selection (all via OpenRouter) ---
    model_coding:         str = field(default_factory=lambda: os.getenv('MODEL_CODING',         'openai/o3'))
    model_business_logic: str = field(default_factory=lambda: os.getenv('MODEL_BUSINESS_LOGIC', 'anthropic/claude-opus-4'))
    model_agent_brain:    str = field(default_factory=lambda: os.getenv('MODEL_AGENT_BRAIN',    'anthropic/claude-sonnet-4-5'))
    model_tool_calling:   str = field(default_factory=lambda: os.getenv('MODEL_TOOL_CALLING',   'meta-llama/llama-3.3-70b-instruct'))
    model_cross_domain:   str = field(default_factory=lambda: os.getenv('MODEL_CROSS_DOMAIN',   'google/gemini-2.5-pro'))
    model_default:        str = field(default_factory=lambda: os.getenv('MODEL_DEFAULT',        'openai/gpt-4o'))
    model_opencode:       str = field(default_factory=lambda: os.getenv('MODEL_OPENCODE',       'openai/o3'))

    # --- LLM general (llama.cpp fallback) ---
    qwen_model_path: str = field(default_factory=lambda: os.getenv('QWEN_MODEL_PATH', ''))
    llm_ctx_size:    int = field(default_factory=lambda: int(os.getenv('LLM_CTX_SIZE', '4096')))
    llm_max_tokens:  int = field(default_factory=lambda: int(os.getenv('LLM_MAX_TOKENS', '2048')))
    llm_seed:        int = field(default_factory=lambda: int(os.getenv('LLM_SEED', '42')))

    # --- Code executor ---
    executor_timeout:   int = field(default_factory=lambda: int(os.getenv('EXECUTOR_TIMEOUT', '5')))
    executor_recursion: int = field(default_factory=lambda: int(os.getenv('EXECUTOR_RECURSION', '100')))

    # --- Tracing ---
    tracing_enabled: bool = field(default_factory=lambda: os.getenv('TRACING_ENABLED', 'true').lower() != 'false')
    checkpoint_dir:  Path = field(default_factory=lambda: Path(os.getenv('CHECKPOINT_DIR', '.checkpoints')))

    # --- API ---
    api_host: str = field(default_factory=lambda: os.getenv('API_HOST', '0.0.0.0'))
    api_port: int = field(default_factory=lambda: int(os.getenv('API_PORT', '8000')))

    # --- MCTS ---
    mcts_simulations:   int = field(default_factory=lambda: int(os.getenv('MCTS_SIMULATIONS', '20')))
    mcts_branch_factor: int = field(default_factory=lambda: int(os.getenv('MCTS_BRANCH_FACTOR', '3')))
    mcts_max_depth:     int = field(default_factory=lambda: int(os.getenv('MCTS_MAX_DEPTH', '4')))

    # --- autoDream ---
    autodream_enabled:      bool = field(default_factory=lambda: os.getenv('AUTODREAM_ENABLED', 'true').lower() != 'false')
    autodream_schedule:     str  = field(default_factory=lambda: os.getenv('AUTODREAM_SCHEDULE', '0 3 * * *'))
    trace_retention_days:    int  = field(default_factory=lambda: int(os.getenv('TRACE_RETENTION_DAYS', '30')))

    # --- KAIROS ---
    kairos_enabled:            bool = field(default_factory=lambda: os.getenv('KAIROS_ENABLED', 'true').lower() != 'false')
    kairos_idle_threshold_minutes: int = field(default_factory=lambda: int(os.getenv('KAIROS_IDLE_THRESHOLD', '5')))
    kairos_dir:               Path = field(default_factory=lambda: Path(os.getenv('KAIROS_DIR', '.kairos')))

    def summary(self) -> dict:
        return {
            'qdrant_url':          self.qdrant_url or '(not set)',
            'neo4j_uri':           self.neo4j_uri or '(not set)',
            'tavily_enabled':      bool(self.tavily_api_key),
            'openrouter_enabled':  bool(self.openrouter_api_key),
            'models': {
                'coding':         self.model_coding,
                'business_logic': self.model_business_logic,
                'agent_brain':    self.model_agent_brain,
                'tool_calling':   self.model_tool_calling,
                'cross_domain':   self.model_cross_domain,
                'default':        self.model_default,
                'opencode':       self.model_opencode,
            },
            'llm_fallback':        self.qwen_model_path or '(stub mode)',
            'tracing':             self.tracing_enabled,
            'checkpoint_dir':      str(self.checkpoint_dir),
            'api':                 f'{self.api_host}:{self.api_port}',
            'mcts_simulations':    self.mcts_simulations,
        }


def reload_config() -> BrainConfig:
    try:
        from dotenv import load_dotenv as _reload
        _reload(override=True)
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
            {"key": "MODEL_CODING", "type": "string", "default": "openai/o3", "label": "Coding Model"},
            {"key": "MODEL_BUSINESS_LOGIC", "type": "string", "default": "anthropic/claude-opus-4", "label": "Business Logic Model"},
            {"key": "MODEL_AGENT_BRAIN", "type": "string", "default": "anthropic/claude-sonnet-4-5", "label": "Agent Brain Model"},
            {"key": "MODEL_TOOL_CALLING", "type": "string", "default": "meta-llama/llama-3.3-70b-instruct", "label": "Tool Calling Model"},
            {"key": "MODEL_CROSS_DOMAIN", "type": "string", "default": "google/gemini-2.5-pro", "label": "Cross-Domain Model"},
            {"key": "MODEL_DEFAULT", "type": "string", "default": "openai/gpt-4o", "label": "Default Model"},
            {"key": "MODEL_OPENCODE", "type": "string", "default": "openai/o3", "label": "OpenCode Model"},
            {"key": "LLM_CTX_SIZE", "type": "int", "default": "4096", "label": "LLM Context Size", "min": 1024, "max": 32768},
            {"key": "LLM_MAX_TOKENS", "type": "int", "default": "2048", "label": "LLM Max Tokens", "min": 256, "max": 16384},
            {"key": "LLM_SEED", "type": "int", "default": "42", "label": "LLM Seed", "min": 0, "max": 9999},
        ],
        "API": [
            {"key": "API_HOST", "type": "string", "default": "0.0.0.0", "label": "API Host"},
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
        if line.strip().startswith(f"{key_upper}=") or line.strip().startswith(f"{key_upper}_"):
            lines[i] = f"{key_upper}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"\n{key_upper}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    return True


cfg = BrainConfig()
