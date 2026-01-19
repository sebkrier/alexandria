from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria"

    # Security
    encryption_key: str = "CHANGE_ME_IN_PRODUCTION"  # For API key encryption

    # Storage (Cloudflare R2)
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "alexandria-files"
    r2_endpoint: str = ""

    # App settings
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars like TEST_DATABASE_URL in CI


@lru_cache
def get_settings() -> Settings:
    return Settings()
