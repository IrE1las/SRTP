"""Application configuration."""

from functools import lru_cache
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = Path(os.environ.get('SRTP_ENV_FILE', str(BASE_DIR / '.env')))
load_dotenv(ENV_FILE)
# Docker's environment is captured when a container is created. Read saved AI
# settings from the mounted file on every process start, including restarts.
if os.environ.get('SRTP_ENV_FILE'):
    for name, value in dotenv_values(ENV_FILE).items():
        if name in {'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'DEEPSEEK_BASE_URL'} and value is not None:
            os.environ[name] = value


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = Field(default="sqlite:///./railway.db", alias="DATABASE_URL")
    secret_key: str = Field(alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_BASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


settings = get_settings()
