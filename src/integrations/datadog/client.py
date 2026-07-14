"""DataDog API client for sending events."""

import httpx
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import time
from fastapi import HTTPException

from ...config import Config
from ...models import NuonWebhook
from .formatters import build_action_event, build_component_event

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
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Type of event ("action" or "component")
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If sending fails
        """
        if event_type == "action":
            return await self.send_action_success_event(webhook)
        elif event_type == "component":
            return await self.send_component_success_event(webhook)
        else:
            logger.error(f"Unknown event type: {event_type}")
            raise HTTPException(
                status_code=500,
                detail=f"Unknown event type: {event_type}"
            )

    # ACTION EVENT METHODS
    async def send_action_success_event(self, webhook: NuonWebhook) -> bool:
        """
        Send an action success event to DataDog.
        
        Args:
            webhook: The parsed Nuon webhook payload
            
        Returns:
            True if successful, False otherwise
        """
        # Determine if this is a workflow summary or step event
        is_workflow_summary = webhook.data.step is None
        
        if is_workflow_summary:
            action_name = "Workflow Summary"
            status_message = "Workflow completed successfully"
        else:
            action_name = webhook.get_action_name() or "Unknown Action"
            status_message = "Action completed successfully"
        duration = webhook.get_duration_seconds()
        
        # Build the DataDog event payload
        event_payload = build_action_event(
            webhook=webhook,
            action_name=action_name,
            status_message=status_message,
            duration=duration
        )
        
        # Send to DataDog
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
                    logger.info(
                        f"Successfully sent event to DataDog for action: {action_name}"
                    )
                    
                    # Also send metrics
                    tags = event_payload.get("tags", [])
                    timestamp = event_payload.get("date_happened")
                    await self.send_metric("nuon.action.count", 1.0, tags, timestamp)
                    
                    # Send duration metric if available
                    if duration:
                        await self.send_metric("nuon.action.duration", duration, tags, timestamp)
                    
                    # Send step_index metric if this is a step event
                    if webhook.data.step:
                        await self.send_metric("nuon.action.step_index", float(webhook.data.step.idx), tags, timestamp)
                    
                    # Send success metric (1 for success, for easy success rate calculation)
                    await self.send_metric("nuon.action.success", 1.0, tags, timestamp)
                    
                    return True
                else:
                    logger.error(
                        f"DataDog API returned {response.status_code}: {response.text}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send event to DataDog: {str(e)}")
            return False

    # COMPONENT EVENT METHODS
    async def send_component_success_event(self, webhook: NuonWebhook) -> bool:
        """
        Send a component deploy success event to DataDog.
        
        Args:
            webhook: The parsed Nuon webhook payload
            
        Returns:
            True if successful, False otherwise
        """
        # Component deploys always have step data
        component_name = webhook.get_component_name() or "Unknown Component"
        status_message = "Component deploy step completed successfully"
        duration = webhook.get_duration_seconds()
        
        # Build the DataDog event payload
        event_payload = build_component_event(
            webhook=webhook,
            component_name=component_name,
            status_message=status_message,
            duration=duration
        )
        
        # Send to DataDog
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
                    logger.info(
                        f"Successfully sent event to DataDog for component: {component_name}"
                    )
                    
                    # Also send metrics
                    tags = event_payload.get("tags", [])
                    timestamp = event_payload.get("date_happened")
                    await self.send_metric("nuon.component.execution.count", 1.0, tags, timestamp)
                    
                    # Send duration metric if available
                    if duration:
                        await self.send_metric("nuon.component.execution.duration", duration, tags, timestamp)
                    
                    # Send step_index metric (component steps always have step data)
                    if webhook.data.step:
                        await self.send_metric("nuon.component.execution.step_index", float(webhook.data.step.idx), tags, timestamp)
                    
                    # Send success metric (1 for success, for easy success rate calculation)
                    await self.send_metric("nuon.component.execution.success", 1.0, tags, timestamp)
                    
                    return True
                else:
                    logger.error(
                        f"DataDog API returned {response.status_code}: {response.text}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send event to DataDog: {str(e)}")
            return False

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
        
        # Build basic tags
        tags = [
            "source:nuon",
            f"kind:{webhook.nuonkind}",
            f"transition:{webhook.nuontransition}",
            f"workflow_type:{webhook.data.workflow.type}",
            f"org_id:{webhook.data.org_id}",
        ]
        
        # Extract resource and op from interests
        for interest in webhook.interests:
            if interest.startswith("resource:") or interest.startswith("op:"):
                tags.append(interest)
        
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
                    await self._send_metric_simple("nuon.webhook.received.count", 1.0, tags, timestamp)
                    
                    # Send duration metric if available
                    if webhook.data.outcome and webhook.data.outcome.duration_ms:
                        await self._send_metric_simple("nuon.webhook.duration", float(webhook.data.outcome.duration_ms), tags, timestamp)
                    
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

    # METRICS METHODS
    async def send_metric(self, metric_name: str, value: float, tags: List[str], timestamp: Optional[int] = None) -> bool:
        """
        Send a metric to DataDog.
        
        Args:
            metric_name: Name of the metric (e.g., 'nuon.action.count')
            value: Numeric value
            tags: List of tags
            timestamp: Unix timestamp (defaults to now)
            
        Returns:
            True if successful, False otherwise
        """
        if timestamp is None:
            timestamp = int(time.time())
        
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
    
    async def _send_metric_simple(self, metric_name: str, value: float, tags: List[str], timestamp: int) -> bool:
        """
        Send a metric to DataDog (simplified version for forwarding mode).
        
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
