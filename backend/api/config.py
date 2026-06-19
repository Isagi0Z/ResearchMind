import os
import sys
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# Resolve .env relative to this file's location (backend/api/config.py -> repo root)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "ResearchMind API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    SECRET_KEY: str
    DATABASE_URL: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    REDIS_URL: str = ""

    CORS_ORIGINS: str = ""
    CORS_ALLOW_CREDENTIALS: bool = True

    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_DOMAIN: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v:
            raise ValueError("SECRET_KEY must not be empty. Set via SECRET_KEY environment variable.")
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters (got {len(v)}). "
                f"Generate a strong key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if v == "testing_secret_key":
            raise ValueError(
                "SECRET_KEY is set to the insecure default 'testing_secret_key'. "
                "Generate a strong key with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "testing", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of: {', '.join(sorted(allowed))} (got '{v}')")
        return v.lower()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.AUTH_COOKIE_SECURE or self.is_production

    model_config = SettingsConfigDict(env_file=_env_path, env_file_encoding="utf-8", extra="ignore")


def validate_environment() -> List[str]:
    warnings: List[str] = []
    if settings.ENVIRONMENT == "production":
        if not settings.cors_origins_list:
            warnings.append("CORS_ORIGINS is empty in production — API will not be accessible from browsers.")
        if not settings.AUTH_COOKIE_SECURE:
            warnings.append("AUTH_COOKIE_SECURE should be True in production for secure cookie transmission.")
        if settings.AUTH_COOKIE_SAMESITE == "none" and not settings.AUTH_COOKIE_SECURE:
            warnings.append("SameSite=None requires Secure flag — cookie will be rejected by browsers.")
        if settings.REFRESH_TOKEN_EXPIRE_DAYS > 30:
            warnings.append("REFRESH_TOKEN_EXPIRE_DAYS > 30 increases risk of prolonged session hijacking.")
    if not settings.DATABASE_URL:
        warnings.append(
            "DATABASE_URL is not set. The default SQLite database will be used, "
            "which lacks the concurrency, connection pooling, and performance characteristics "
            "needed for production. Set DATABASE_URL to a PostgreSQL connection string."
        )
    elif "postgresql" not in settings.DATABASE_URL and settings.ENVIRONMENT == "production":
        warnings.append(
            f"DATABASE_URL ({settings.DATABASE_URL}) does not appear to be a PostgreSQL URL. "
            "Production deployments should use PostgreSQL with asyncpg driver."
        )
    return warnings

try:
    settings = Settings()
except Exception as e:
    print("FATAL: Failed to load application configuration.", file=sys.stderr)
    print(f"  {e}", file=sys.stderr)
    print("\nRequired configuration:", file=sys.stderr)
    print("  SECRET_KEY     (required, min 32 characters, set as env var or in .env)", file=sys.stderr)
    print("  DATABASE_URL   (optional, defaults to sqlite+aiosqlite:///./test.db)", file=sys.stderr)
    print("\nQuick start — generate a SECRET_KEY and create a .env file:", file=sys.stderr)
    print('  echo "SECRET_KEY=$(python -c \"import secrets; print(secrets.token_hex(32))\")" > .env', file=sys.stderr)
    sys.exit(1)

# Module-level aliases for backward compatibility with existing imports
SECRET_KEY = settings.SECRET_KEY
ENVIRONMENT = settings.ENVIRONMENT
