# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    db_dsn: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    cors_origins: list[str] = ["http://localhost:3000"] # Default for local Next.js dev

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()