"""Validated authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator

from app.core.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address")
        return normalized


class UserResponse(BaseModel):
    id: UUID
    email: str
    roles: list[str]


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class LogoutResponse(BaseModel):
    status: str


class AccessResponse(BaseModel):
    access: str
    role: str
