"""
config.py - Quản lý cấu hình ứng dụng
Sử dụng pydantic-settings để load biến môi trường từ .env
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng"""

    # === Vertex AI ===
    vertex_project_id: str = "xiaoyue-api"
    vertex_location: str = "us-central1"
    vertex_credentials_path: str = os.path.join(os.path.dirname(__file__), "xiaoyue-api-key.json")

    # === Database ===
    database_url: str = "postgresql://aia_user:aia_secret_2024@localhost:5433/aia_db"
    encryption_key: str = "AIA_SUPER_SECRET_KEY_FOR_FERNET_32_BYTES"

    # === Gmail OAuth2 (Phase 3) ===
    gmail_client_id: str = ""
    gmail_client_secret: str = ""

    # === App Settings ===
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    # === LLM Settings ===
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"

    # === Voice (TTS & STT) ===
    tts_model: str = "gemini-2.5-flash-tts"
    tts_voice: str = "Leda"
    tts_language: str = "vi-VN"
    stt_language: str = "vi-VN"

    # === Vertex AI Search (Discovery Engine) ===
    vertex_search_data_store_id: str = "aia-ds_1774321984667"
    data_store_credentials_path: str = os.path.join(os.path.dirname(__file__), "data-store-key.json")

    # === Vector Store ===
    embedding_dimension: int = 3072  # gemini-embedding-001 dimension
    collection_name: str = "aia_user_memory"

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Singleton pattern cho Settings"""
    settings = Settings()
    if settings.vertex_credentials_path and os.path.exists(settings.vertex_credentials_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.vertex_credentials_path
    return settings
