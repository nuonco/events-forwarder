"""Configuration management for environment variables and app settings."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file if running locally (ignored in production/Fly.io)
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # DataDog API credentials
    DATADOG_API_KEY: str = os.getenv("DATADOG_API_KEY", "")
    DATADOG_APP_KEY: str = os.getenv("DATADOG_APP_KEY", "")
    
    # Nuon webhook verification secret
    NUON_WEBHOOK_SECRET: Optional[str] = os.getenv("NUON_WEBHOOK_SECRET")
    
    # DataDog API endpoints (US5 region)
    DATADOG_EVENTS_URL: str = "https://api.us5.datadoghq.com/api/v1/events"
    DATADOG_METRICS_URL: str = "https://api.us5.datadoghq.com/api/v2/series"
    
    # Grafana Cloud API credentials
    GRAFANA_METRICS_URL: str = os.getenv("GRAFANA_METRICS_URL", "")
    GRAFANA_INSTANCE_ID: str = os.getenv("GRAFANA_INSTANCE_ID", "")
    GRAFANA_API_TOKEN: str = os.getenv("GRAFANA_API_TOKEN", "")
    
    # App settings
    PORT: int = int(os.getenv("PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# Note: Validation is now handled per-integration via the enabled flag
# This allows running the app with only some integrations configured
