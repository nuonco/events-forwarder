"""DataDog API client for sending events."""

import httpx
import logging
import json
import time
from fastapi import HTTPException

from ...config import Config
from ...models import NuonWebhook

logger = logging.getLogger(__name__)


class DataDogClient:
    """Client for sending events to DataDog API."""

    def __init__(self):
        """Initialize the DataDog client with API credentials."""
        self.api_key = Config.DATADOG_API_KEY
        self.app_key = Config.DATADOG_APP_KEY
        self.events_url = Config.DATADOG_EVENTS_URL
        self.metrics_url = Config.DATADOG_METRICS_URL

    # BASE INTEGRATION INTERFACE
    async def send(self, webhook: NuonWebhook, event_type: str) -> bool:
        """
        Send webhook to DataDog (implements BaseIntegration interface).
        
        Forwards webhook as JSON blob with basic tags and metrics.
        Works automatically for all webhook types.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Not used (kept for interface compatibility)
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        return await self._send_forward(webhook)

    # FORWARDING METHOD
    async def _send_forward(self, webhook: NuonWebhook) -> bool:
        """
        Forward webhook to DataDog with minimal processing.
        
        Sends generic event with JSON blob message and basic tags.
        Works automatically for all webhook types.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # Build generic title
        title = f"Nuon {webhook.nuonkind} - {webhook.nuontransition}"
        
        # Convert webhook to JSON blob
        text = json.dumps(webhook.dict(), indent=2)
        
        # Build rich tags (matching Grafana labels)
        tags = [
            "source:nuon",
            f"kind:{webhook.nuonkind}",
            f"transition:{webhook.nuontransition}",
            f"workflow_type:{webhook.data.workflow.type}",
            f"workflow_id:{webhook.data.workflow.id}",
            f"install_id:{webhook.data.workflow.owner_id}",
            f"org_id:{webhook.data.org_id}",
        ]
        
        # Extract resource and operation from interests
        for interest in webhook.interests:
            if interest.startswith("resource:"):
                tags.append(f"resource:{interest.split(':', 1)[1]}")
            elif interest.startswith("op:"):
                tags.append(f"operation:{interest.split(':', 1)[1]}")
        
        # Add step-specific tags if this is a step event
        if webhook.data.step:
            tags.extend([
                f"step_id:{webhook.data.step.id}",
                f"step_name:{webhook.data.step.name}",
                f"step_idx:{webhook.data.step.idx}",
                f"execution_type:{webhook.data.step.execution_type}",
            ])
            
            # Add component_id if available
            if webhook.data.step.component_id:
                tags.append(f"component_id:{webhook.data.step.component_id}")
        
        # Add outcome status if terminal
        if webhook.data.outcome and webhook.data.outcome.status:
            tags.append(f"outcome_status:{webhook.data.outcome.status}")
        
        # Build event payload
        event_payload = {
            "title": title,
            "text": text,
            "tags": tags,
            "alert_type": "info",
        }
        
        # Send event to DataDog
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.events_url,
                    json=event_payload,
                    headers={
                        "DD-API-KEY": self.api_key,
                        "DD-APPLICATION-KEY": self.app_key,
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 202]:
                    logger.info(f"Successfully forwarded event to DataDog: {title}")
                    
                    # Send generic count metric
                    timestamp = int(time.time())
                    await self._send_metric("nuon.webhook.received.count", 1.0, tags, timestamp)
                    
                    # Send duration metric if available
                    if webhook.data.outcome and webhook.data.outcome.duration_ms:
                        await self._send_metric("nuon.webhook.duration", float(webhook.data.outcome.duration_ms), tags, timestamp)
                    
                    return True
                else:
                    logger.error(f"DataDog API returned {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to forward event to DataDog: {response.status_code}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to forward event to DataDog: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to forward event to DataDog: {str(e)}"
            )

    # METRICS METHOD
    async def _send_metric(self, metric_name: str, value: float, tags: list, timestamp: int) -> bool:
        """
        Send a metric to DataDog.
        
        Args:
            metric_name: Name of the metric
            value: Numeric value
            tags: List of tags
            timestamp: Unix timestamp
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "series": [
                {
                    "metric": metric_name,
                    "type": 0,  # gauge
                    "points": [
                        {
                            "timestamp": timestamp,
                            "value": value
                        }
                    ],
                    "tags": tags
                }
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.metrics_url,
                    json=payload,
                    headers={
                        "DD-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )
                
                if response.status_code in [200, 202]:
                    logger.debug(f"Successfully sent metric {metric_name} to DataDog")
                    return True
                else:
                    logger.error(f"DataDog Metrics API returned {response.status_code}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send metric to DataDog: {str(e)}")
            return False
