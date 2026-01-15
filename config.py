"""Configuration management using environment variables."""
from typing import Optional
import os
from pydantic import BaseModel


class Settings(BaseModel):
    """
    Simple settings object populated from environment variables.

    Using a regular Pydantic BaseModel here avoids issues with
    pydantic-settings while still giving us type safety.
    """

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    webhook_secret: Optional[str] = os.getenv("WEBHOOK_SECRET")

    def validate_webhook_secret(self) -> None:
        """Validate that WEBHOOK_SECRET is set."""
        if not self.webhook_secret:
            raise ValueError("WEBHOOK_SECRET environment variable must be set")


# Global settings instance
settings = Settings()

