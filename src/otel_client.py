"""OpenTelemetry client for sending logs to OTel Collector."""

import httpx
import logging
import json
import time
from fastapi import HTTPException

from ...config import Config
from ...models import NuonWebhook

logger = logging.getLogger(__name__)


class OtelClient:
    """Client for sending logs to OpenTelemetry Collector."""

    def __init__(self):
        """Initialize the OTel client with collector endpoint."""
        self.endpoint = Config.OTEL_COLLECTOR_ENDPOINT
        self.enabled = True
        logger.info(f"OTel client initialized, sending to {self.endpoint}")

    async def send(self, webhook: NuonWebhook, event_type: str) -> bool:
        """
        Send webhook as OTel log to collector.
        
        Converts Nuon webhook to OpenTelemetry log format and sends to collector.
        No attributes/labels - just raw webhook JSON in log body.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Not used (kept for interface compatibility)
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        # Build OTel log format
        log_entry = self._build_otel_log(webhook)
        
        # Send to OTel Collector
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/v1/logs",
                    json=log_entry,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0
                )
                
                if response.status_code in [200, 202]:
                    logger.info(f"Successfully sent log to OTel Collector: {webhook.nuonkind} - {webhook.nuontransition}")
                    return True
                else:
                    logger.error(f"OTel Collector returned {response.status_code}: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to send log to OTel Collector: {response.status_code}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to send to OTel Collector: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send to OTel Collector: {str(e)}"
            )

    def _build_otel_log(self, webhook: NuonWebhook) -> dict:
        """
        Build OpenTelemetry log format from webhook.
        
        Creates OTLP/HTTP JSON log format with webhook as body.
        No attributes - keeping it minimal for now.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            Dictionary in OTLP log format
        """
        # Current time in nanoseconds (OTel format)
        time_unix_nano = str(int(time.time() * 1_000_000_000))
        
        # Convert webhook to JSON string for log body
        webhook_json = json.dumps(webhook.dict())
        
        # Build OTLP log format
        # https://opentelemetry.io/docs/specs/otlp/#otlphttp
        return {
            "resourceLogs": [{
                "resource": {
                    "attributes": [{
                        "key": "service.name",
                        "value": {"stringValue": "nuon-events-forwarder"}
                    }]
                },
                "scopeLogs": [{
                    "scope": {
                        "name": "nuon.webhooks"
                    },
                    "logRecords": [{
                        "timeUnixNano": time_unix_nano,
                        "severityText": "INFO",
                        "body": {
                            "stringValue": webhook_json
                        }
                        # No attributes - just raw webhook in body
                    }]
                }]
            }]
        }
