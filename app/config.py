"""Typed configuration for the listing platform (environment driven)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Every setting maps to an upper-case environment variable."""

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_KEY: str = ""  # when set, /api/v1 requires X-API-Key
    BACKEND_ORIGINS: str = "http://localhost:5173"

    DATA_DIR: str = str(ROOT_DIR / "data")
    DB_PATH: str = str(ROOT_DIR / "data" / "kitsunecart.db")
    UPLOAD_DIR: str = str(ROOT_DIR / "data" / "uploads")

    # LLM provider: "groq" | "mock" (deterministic, used by the tests)
    LLM_PROVIDER: str = "mock"
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.1-8b-instant"

    # Vision provider: "mock" | "openai"
    VISION_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    VISION_MODEL: str = "gpt-4o-mini"

    # Marketplace publishing
    MARKETPLACES: str = "amazon_in,flipkart,meesho"
    PUBLISH_ENABLED: bool = False

    # Business rules
    DEFAULT_CURRENCY: str = "INR"
    TARGET_MARGIN_PCT: float = 18.0
    MIN_MARGIN_PCT: float = 8.0
    SUPPORTED_LANGUAGES: str = "en,hi,mr,ta,te,bn,kn,ml,gu,pa"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def marketplace_list(self) -> list[str]:
        return [item.strip() for item in self.MARKETPLACES.split(",") if item.strip()]

    @property
    def language_list(self) -> list[str]:
        return [item.strip() for item in self.SUPPORTED_LANGUAGES.split(",") if item.strip()]


settings = Settings()
