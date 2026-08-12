"""
app/core/config.py

Centralised application settings using Pydantic-Settings.
All values are loaded from environment variables or a .env file.
"""
from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    DEBUG: bool = False
    
    # ── Patent Pipeline ──────────────────────────────────────────────────────
    TARGET_PATENTS: int = 15
    MIN_REQUIRED_PATENTS: int = 5
    MAX_SEARCH_RESULTS: int = 100
    MAX_SEARCH_PAGES_PER_QUERY: int = 3
    TOP_LLM_CANDIDATES: int = 30
    MAX_FINAL_PATENTS: int = 15
    MAX_PATENT_DOWNLOADS: int = 15
    SEARCH_CACHE_TTL_DAYS: int = 30
    SEARCH_CACHE_VERSION: int = 1
    BYPASS_SEARCH_CACHE: bool = False
    
    # ── Budgets & Circuit Breakers ──
    MAX_EXTRACTION_INPUT_TOKENS: int = 5000
    GLOBAL_TOKEN_BUDGET: int = 30000
    PRIMARY_LLM: str = "groq"
    FALLBACK_LLM: str = "groq"
    ENABLE_FALLBACK: bool = True
    MAX_EXTRACTION_CALLS: int = 15
    MAX_TOTAL_LLM_CALLS: int = 20

    # 🤖 LLM Settings 🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── AI API Keys (placeholders for Phase 2) ───────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    SERPER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROK_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Apcotex R&D API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if not v or v == "your-super-secret-key-change-in-production-min-32-chars":
            raise ValueError("SECRET_KEY must be set to a strong random value.")
        return v

    @model_validator(mode="after")
    def validate_llm_keys(self):
        # We now validate API keys at runtime via provider_registry.py
        # when a specific provider is requested.
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


settings: Settings = get_settings()
