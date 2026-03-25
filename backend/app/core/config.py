"""ExecMind - Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ExecMind"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://execmind:execmind@localhost:5432/execmind"

    # JWT
    JWT_PRIVATE_KEY_PATH: str = "/keys/private.pem"
    JWT_PUBLIC_KEY_PATH: str = "/keys/public.pem"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "RS256"

    # Ollama
    OLLAMA_URL: str = "http://ollama:11434"
    OLLAMA_API_KEY: str = ""
    LLM_MODEL: str = "qwen3.5:9b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_REQUEST_TIMEOUT: float = 30.0
    LLM_TEMPERATURE: float = 0.1

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_VECTOR_SIZE: int = 768
    QDRANT_SIMILARITY_TOP_K: int = 5

    # Encryption
    MASTER_ENCRYPTION_KEY: str = ""

    # File Upload
    MAX_FILE_SIZE_MB: int = 50
    DOCUMENT_STORAGE_PATH: str = "/data/documents"

    # Brute Force Protection
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # Conversation
    CONVERSATION_CONTEXT_WINDOW: int = 20
    LLM_CONTEXT_WINDOW: int = 131072

    # Agentic Tool System
    TOOLS_CONFIG_PATH: str = "config.yaml"  # Relative to backend root
    AGENT_MAX_TOOL_ITERATIONS: int = 5  # Override; config.yaml takes precedence if set

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB to bytes for file upload validation."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.APP_ENV == "development"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
