import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "ResearchMind API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    RATE_LIMIT_REQUESTS: int = 1000
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    REDIS_URL: str = ""

    CORS_ORIGINS: List[AnyHttpUrl] = []

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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
