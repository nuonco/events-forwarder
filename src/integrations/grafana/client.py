"""Grafana Cloud client for sending metrics."""

import logging
import time
import base64
from typing import List, Dict, Any
from fastapi import HTTPException
from prometheus_client import CollectorRegistry, Gauge
from prometheus_client.exposition import basic_auth_handler
from prometheus_client.openmetrics.exposition import generate_latest
import httpx

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
        # Extract metrics and labels
        metrics = self._extract_metrics(webhook)
        labels = self._build_labels(webhook)
        timestamp = int(time.time())
        
        # Send to Grafana
        return await self._send_to_grafana(metrics, labels, timestamp)

    # METRICS EXTRACTION
    def _extract_metrics(self, webhook: NuonWebhook) -> List[Dict[str, Any]]:
        """
        Extract numeric metrics from webhook.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            List of metric dictionaries with name and value
        """
        metrics = []
        
        # Always send count metric
        metrics.append({
            "name": "nuon_webhook_count",
            "value": 1.0
        })
        
        # Add duration metric if available
        if webhook.data.outcome and webhook.data.outcome.duration_ms is not None:
            metrics.append({
                "name": "nuon_webhook_duration_ms",
                "value": float(webhook.data.outcome.duration_ms)
            })
        
        # Add success metric if terminal state
        if webhook.data.outcome and webhook.data.outcome.status:
            success_value = 1.0 if webhook.data.outcome.status == "succeeded" else 0.0
            metrics.append({
                "name": "nuon_webhook_success",
                "value": success_value
            })
        
        return metrics

    # LABELS BUILDER
    def _build_labels(self, webhook: NuonWebhook) -> Dict[str, str]:
        """
        Build labels (Grafana's version of tags) from webhook.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            Dictionary of label key-value pairs
        """
        labels = {
            # Always available
            "source": "nuon",
            "kind": webhook.nuonkind,
            "transition": webhook.nuontransition,
            "workflow_id": webhook.data.workflow.id,
            "workflow_type": webhook.data.workflow.type,
            "install_id": webhook.data.workflow.owner_id,
            "org_id": webhook.data.org_id,
        }
        
        # Extract resource and operation from interests
        for interest in webhook.interests:
            if interest.startswith("resource:"):
                labels["resource"] = interest.split(":", 1)[1]
            elif interest.startswith("op:"):
                labels["operation"] = interest.split(":", 1)[1]
        
        # Add step-specific labels if this is a step event
        if webhook.data.step:
            labels["step_id"] = webhook.data.step.id
            labels["step_name"] = webhook.data.step.name
            labels["step_idx"] = str(webhook.data.step.idx)
            labels["execution_type"] = webhook.data.step.execution_type
            
            # Add component_id if available
            if webhook.data.step.component_id:
                labels["component_id"] = webhook.data.step.component_id
        
        # Add outcome status if terminal
        if webhook.data.outcome and webhook.data.outcome.status:
            labels["outcome_status"] = webhook.data.outcome.status
        
        return labels

    # SEND TO GRAFANA
    async def _send_to_grafana(self, metrics: List[Dict[str, Any]], labels: Dict[str, str], timestamp: int) -> bool:
        """
        Send metrics to Grafana Cloud Prometheus endpoint.
        
        Uses Prometheus Remote Write format (Protobuf + Snappy).
        
        Args:
            metrics: List of metric dictionaries
            labels: Label key-value pairs
            timestamp: Unix timestamp
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # Create a temporary registry for these metrics
        registry = CollectorRegistry()
        
        # Get label names and values
        label_names = list(labels.keys())
        label_values = list(labels.values())
        
        # Create and set each metric
        for metric in metrics:
            gauge = Gauge(
                metric["name"],
                f"Nuon webhook metric: {metric['name']}",
                labelnames=label_names,
                registry=registry
            )
            gauge.labels(*label_values).set(metric["value"])
        
        # Generate Prometheus exposition format
        metrics_data = generate_latest(registry)
        
        # Build Basic Auth header (base64-encoded)
        auth_string = f"{self.instance_id}:{self.api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.metrics_url,
                    content=metrics_data,
                    headers={
                        "Authorization": f"Basic {auth_b64}",
                        "Content-Type": "application/openmetrics-text",
                        "X-Prometheus-Remote-Write-Version": "0.1.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully sent {len(metrics)} metrics to Grafana")
                    return True
                else:
                    logger.error(f"Grafana API returned {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to send metrics to Grafana: {response.status_code}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send metrics to Grafana: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send metrics to Grafana: {str(e)}"
            )
