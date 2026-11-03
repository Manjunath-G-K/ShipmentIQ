"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="ShipmentIQ API", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: str = Field(validation_alias="DATABASE_URL")
    db_connect_timeout: int = Field(default=3, validation_alias="DB_CONNECT_TIMEOUT")
    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256", validation_alias="JWT_ALGORITHM"
    )
    jwt_issuer: str = Field(default="shipmentiq", validation_alias="JWT_ISSUER")
    jwt_audience: str = Field(
        default="shipmentiq-api", validation_alias="JWT_AUDIENCE"
    )
    jwt_expire_minutes: int = Field(
        default=30, validation_alias="JWT_EXPIRE_MINUTES"
    )
    auth_cookie_name: str = Field(
        default="shipmentiq_session", validation_alias="AUTH_COOKIE_NAME"
    )
    auth_cookie_secure: bool = Field(
        default=False, validation_alias="AUTH_COOKIE_SECURE"
    )
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", validation_alias="AUTH_COOKIE_SAMESITE"
    )
    auth_csrf_cookie_name: str = Field(
        default="shipmentiq_csrf", validation_alias="AUTH_CSRF_COOKIE_NAME"
    )
    auth_csrf_header_name: str = Field(
        default="X-CSRF-Token", validation_alias="AUTH_CSRF_HEADER_NAME"
    )
    auth_allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="AUTH_ALLOWED_ORIGINS",
    )
    seed_demo_users: bool = Field(
        default=False, validation_alias="SEED_DEMO_USERS"
    )
    demo_executive_email: str | None = Field(
        default=None, validation_alias="DEMO_EXECUTIVE_EMAIL"
    )
    demo_executive_password: str | None = Field(
        default=None, validation_alias="DEMO_EXECUTIVE_PASSWORD"
    )
    demo_manager_email: str | None = Field(
        default=None, validation_alias="DEMO_MANAGER_EMAIL"
    )
    demo_manager_password: str | None = Field(
        default=None, validation_alias="DEMO_MANAGER_PASSWORD"
    )

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        """Prevent accidental use of SQLite or another unsupported database."""

        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver")
        return value

    @field_validator("db_connect_timeout")
    @classmethod
    def require_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DB_CONNECT_TIMEOUT must be greater than zero")
        return value

    @field_validator("jwt_expire_minutes")
    @classmethod
    def require_positive_jwt_expiry(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JWT_EXPIRE_MINUTES must be greater than zero")
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def require_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return value

    @field_validator("auth_allowed_origins")
    @classmethod
    def require_allowed_origin(cls, value: str) -> str:
        if not {origin.strip() for origin in value.split(",") if origin.strip()}:
            raise ValueError("AUTH_ALLOWED_ORIGINS must contain at least one origin")
        return value

    @model_validator(mode="after")
    def require_secure_production_cookies(self) -> "Settings":
        if self.environment.lower() == "production" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be true in production")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be true with SameSite=None")
        return self

    def allowed_origins(self) -> set[str]:
        """Return normalized origins allowed for state-changing requests."""

        return {
            origin.strip()
            for origin in self.auth_allowed_origins.split(",")
            if origin.strip()
        }


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""

    return Settings()
