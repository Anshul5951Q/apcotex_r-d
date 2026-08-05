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

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── AI API Keys (placeholders for Phase 2) ───────────────────────────────
    GEMINI_API_KEY: str = ""
    SERPER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
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
        if not self.GEMINI_API_KEY:
            raise ValueError("Startup Validation Failed: GEMINI_API_KEY is missing from environment variables.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


settings: Settings = get_settings()
