"""Shared test setup."""

import os

# Keep test configuration explicit and never depend on a developer's local .env.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test_user:test_password@localhost:5432/test_db",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-for-production")
os.environ.setdefault("AUTH_ALLOWED_ORIGINS", "http://testserver")
