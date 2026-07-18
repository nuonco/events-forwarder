"""Configuration management for environment variables and app settings."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file if running locally (ignored in production/Fly.io)
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Nuon webhook verification secret
    NUON_WEBHOOK_SECRET: Optional[str] = os.getenv("NUON_WEBHOOK_SECRET")
    
    # OpenTelemetry Collector endpoint
    OTEL_COLLECTOR_ENDPOINT: str = os.getenv("OTEL_COLLECTOR_ENDPOINT", "http://localhost:4318")
    
    # App settings
    PORT: int = int(os.getenv("PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# Note: Validation is now handled per-integration via the enabled flag
# This allows running the app with only some integrations configured
