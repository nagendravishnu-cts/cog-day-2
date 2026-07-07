"""Application configuration using environment variables."""

import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./test.db"
    )
    
    # Redis
    REDIS_URL: str = os.getenv(
        "REDIS_URL", "redis://localhost:6379/0"
    )
    REDIS_EVENT_TTL: int = int(os.getenv("REDIS_EVENT_TTL", "86400"))  # 24 hours in seconds
    
    # Application
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_TITLE: str = "Stripe Webhook Processor"
    API_VERSION: str = "1.0.0"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
