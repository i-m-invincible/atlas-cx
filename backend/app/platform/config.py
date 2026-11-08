from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    public_origin: str = "http://localhost:5173"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://atlas_app:local-app-only@localhost:5432/atlas_cx"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    default_timezone: str = "Asia/Kolkata"

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("Use a PostgreSQL psycopg connection URL")
        return value

    @field_validator("public_origin")
    @classmethod
    def origin_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PUBLIC_ORIGIN must be an HTTP origin without a path")
        return value.rstrip("/")

    @field_validator("default_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
