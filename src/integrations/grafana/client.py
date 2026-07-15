"""Grafana Cloud client for sending metrics."""

import httpx
import logging
from fastapi import HTTPException

from ...config import Config
from ...models import NuonWebhook

logger = logging.getLogger(__name__)


class GrafanaClient:
    """Client for sending metrics to Grafana Cloud Prometheus."""

    def __init__(self):
        """Initialize the Grafana client with API credentials."""
        self.metrics_url = Config.GRAFANA_METRICS_URL
        self.instance_id = Config.GRAFANA_INSTANCE_ID
        self.api_token = Config.GRAFANA_API_TOKEN

    # BASE INTEGRATION INTERFACE
    async def send(self, webhook: NuonWebhook, event_type: str) -> bool:
        """
        Send webhook to Grafana (implements BaseIntegration interface).
        
        Extracts metrics from webhook and sends to Grafana Cloud.
        Works automatically for all webhook types.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Not used (kept for interface compatibility)
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # TODO: Implement in next commit
        pass

    # METRICS EXTRACTION
    def _extract_metrics(self, webhook: NuonWebhook) -> list:
        """
        Extract numeric metrics from webhook.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            List of metric dictionaries with name and value
        """
        # TODO: Implement in next commit
        pass

    # LABELS BUILDER
    def _build_labels(self, webhook: NuonWebhook) -> dict:
        """
        Build labels (Grafana's version of tags) from webhook.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            Dictionary of label key-value pairs
        """
        # TODO: Implement in next commit
        pass

    # SEND TO GRAFANA
    async def _send_to_grafana(self, metrics: list, labels: dict, timestamp: int) -> bool:
        """
        Send metrics to Grafana Cloud Prometheus endpoint.
        
        Args:
            metrics: List of metric dictionaries
            labels: Label key-value pairs
            timestamp: Unix timestamp
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # TODO: Implement in next commit
        pass
