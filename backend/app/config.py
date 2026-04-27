from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    dashscope_api_key: str | None = os.getenv("DASHSCOPE_API_KEY")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:////data/vibe.db")
    public_backend_url: str = os.getenv(
        "PUBLIC_BACKEND_URL",
        "https://vibe-marketing-backen-yzgloorg.fly.dev",
    )
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    text_model: str = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
    pro_model: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-flash")
    image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
