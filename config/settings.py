"""Environment-based configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment-based configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # LLM Provider Settings
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None

    # Default LLM Configuration
    default_llm_provider: Literal["openai", "anthropic", "azure_openai"] = "openai"
    default_model: str = "gpt-4o"
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    default_max_tokens: int = Field(default=4096, ge=1, le=128000)

    # Vector Database Configuration
    vector_db_provider: Literal["chroma", "pinecone", "faiss"] = "chroma"
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "agentic_ai"

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    dynamodb_table_name: str = "agent-state"
    s3_bucket_name: str = "agent-artifacts"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_key_header: str = "X-API-Key"
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60

    # HITL Configuration
    hitl_enabled: bool = True
    hitl_timeout_seconds: int = 3600
    hitl_notification_email: Optional[str] = None
    hitl_slack_webhook_url: Optional[str] = None
    hitl_webhook_secret: str = "change-me-in-production"

    # Observability
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "agentic-ai-starter"
    cloudwatch_enabled: bool = False

    # Security
    enable_cors: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    pii_detection_enabled: bool = True
    input_sanitization_enabled: bool = True

    # Feature Flags
    enable_parallel_execution: bool = True
    enable_reflection_loops: bool = True
    enable_tool_caching: bool = True

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info: any) -> str:
        """Validate JWT secret key in production."""
        if info.data.get("environment") == "production" and v == "change-me-in-production":
            raise ValueError("JWT secret key must be changed in production environment")
        return v

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

