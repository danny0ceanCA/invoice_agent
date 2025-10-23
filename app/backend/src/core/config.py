"""Application configuration utilities."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings derived from environment variables."""

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    database_url: str = Field(
        default="sqlite:///./invoice.db", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str | None = Field(
        default=None, alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str | None = Field(
        default=None, alias="CELERY_RESULT_BACKEND"
    )
    aws_region: str = Field(default="us-west-1", alias="AWS_REGION")
    aws_s3_bucket: str = Field(default="local", alias="AWS_S3_BUCKET")
    aws_access_key_id: str | None = Field(
        default=None, alias="AWS_ACCESS_KEY_ID"
    )
    aws_secret_access_key: str | None = Field(
        default=None, alias="AWS_SECRET_ACCESS_KEY"
    )
    local_storage_path: str = Field(
        default="/tmp/invoice-agent", alias="LOCAL_STORAGE_PATH"
    )

    model_config = {"case_sensitive": False}

    def get(self, key: str, default: object | None = None) -> object | None:
        """Dictionary-style access to configuration values."""

        return self.model_dump(by_alias=True).get(key, default)

    @property
    def broker_url(self) -> str:
        """Return the Celery broker URL, defaulting to Redis."""

        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        """Return the Celery result backend, defaulting to Redis DB 1."""

        if self.celery_result_backend:
            return self.celery_result_backend
        if self.redis_url.endswith("/0"):
            return f"{self.redis_url[:-2]}/1"
        return self.redis_url

    @property
    def redis_enabled(self) -> bool:
        """Return ``True`` when Redis integrations should be used."""

        return str(self.get("REDIS_ENABLED", "true")).lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


__all__ = ["Settings", "get_settings"]
