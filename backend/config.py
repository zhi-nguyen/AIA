"""
config.py - Quản lý cấu hình ứng dụng
Sử dụng pydantic-settings để load biến môi trường từ .env
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng"""

    # === Gemini API ===
    gemini_api_key: str = ""

    # === Database ===
    database_url: str = "postgresql://aia_user:aia_secret_2024@localhost:5433/aia_db"

    # === Gmail OAuth2 (Phase 3) ===
    gmail_client_id: str = ""
    gmail_client_secret: str = ""

    # === App Settings ===
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    # === LLM Settings ===
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"

    # === Vector Store ===
    embedding_dimension: int = 768  # Google embedding dimension
    collection_name: str = "aia_user_memory"

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Singleton pattern cho Settings"""
    return Settings()
