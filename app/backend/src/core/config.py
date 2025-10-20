"""Application configuration utilities."""

from __future__ import annotations

from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Settings derived from environment variables."""

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    database_url: str = Field(default="postgresql+psycopg2://user:pass@localhost:5432/db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    aws_region: str = Field(default="us-west-1", alias="AWS_REGION")
    aws_s3_bucket: str = Field(default="scusd-invoices", alias="AWS_S3_BUCKET")

    model_config = {"case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
