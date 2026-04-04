from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Immortality"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/immortality"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/immortality"
    SECRET_KEY: str = "change-this-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HUME_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    VOICE_STORAGE_PATH: str = "voice_storage" 
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    VOICE_ENABLED: str = "false"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
