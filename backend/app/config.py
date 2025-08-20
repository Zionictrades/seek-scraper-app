# backend/app/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    SEEK_BASE_URL: str = "https://www.seek.com.au"

    # Make DB optional so app can run in REST-only mode
    DB_DSN: Optional[str] = None

settings = Settings()