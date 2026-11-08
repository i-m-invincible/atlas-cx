from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
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
    session_signing_key: SecretStr = SecretStr(
        "local-development-session-key-change-before-hosting"
    )
    cursor_signing_key: SecretStr = SecretStr("local-development-cursor-key-change-before-hosting")

    @model_validator(mode="after")
    def secure_configuration(self) -> "Settings":
        for key in (self.session_signing_key, self.cursor_signing_key):
            value = key.get_secret_value()
            if len(value) < 32:
                raise ValueError("Signing keys must contain at least 32 characters")
            if self.app_env == "production" and value.startswith("local-development-"):
                raise ValueError("Production requires independently generated signing keys")
        if self.app_env == "production" and not self.public_origin.startswith("https://"):
            raise ValueError("Production requires an HTTPS origin")
        return self

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
