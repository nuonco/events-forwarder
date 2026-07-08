"""DataDog API client for sending events."""

import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .config import Config
from .models import NuonWebhook

logger = logging.getLogger(__name__)


class DataDogClient:
    """Client for sending events to DataDog API."""

    def __init__(self):
        """Initialize the DataDog client with API credentials."""
        self.api_key = Config.DATADOG_API_KEY
        self.app_key = Config.DATADOG_APP_KEY
        self.api_url = Config.DATADOG_API_URL

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
        event_payload = self._build_event_payload(
            webhook=webhook,
            action_name=action_name,
            status_message=status_message,
            duration=duration
        )
        
        # Send to DataDog
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
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
                    return True
                else:
                    logger.error(
                        f"DataDog API returned {response.status_code}: {response.text}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send event to DataDog: {str(e)}")
            return False

    def _build_event_payload(
        self,
        webhook: NuonWebhook,
        action_name: str,
        status_message: str,
        duration: Optional[float]
    ) -> Dict[str, Any]:
        """
        Build the DataDog event payload.
        
        Args:
            webhook: The parsed Nuon webhook
            action_name: Name of the successful action
            status_message: Success status message
            duration: Duration in seconds (if available)
            
        Returns:
            Dictionary formatted for DataDog Events API
        """
        # Build event title based on event type
        is_workflow_summary = webhook.data.step is None
        if is_workflow_summary:
            title = "✅ Nuon Action Workflow Complete"
        else:
            title = f"✅ Nuon Action Succeeded: {action_name}"
        
        # Build event text with details
        text_parts = [
            f"Action: {action_name}",
            f"Status: {webhook.data.transition}",
            f"Message: {status_message}",
        ]
        
        if duration:
            text_parts.append(f"Duration: {duration:.2f}s")
        
        # Add Org ID, Install ID, Workflow ID and Workflow Type
        text_parts.append(f"Org ID: {webhook.data.org_id}")
        text_parts.append(f"Install ID: {webhook.data.workflow.owner_id}")
        text_parts.append(f"Workflow ID: {webhook.data.workflow.id}")
        text_parts.append(f"Workflow Type: {webhook.data.workflow.type}")
        
        if webhook.data.step:
            text_parts.append(f"Step ID: {webhook.data.step.id}")
            text_parts.append(f"Step Index: {webhook.data.step.idx}")
            if webhook.data.step.target_type:
                text_parts.append(f"Target Type: {webhook.data.step.target_type}")
            if webhook.data.step.target_id:
                text_parts.append(f"Target ID: {webhook.data.step.target_id}")
            text_parts.append(f"Execution Type: {webhook.data.step.execution_type}")
        
        # Add links to Nuon dashboard
        if webhook.data.links:
            links = webhook.data.links
            if links.workflow:
                text_parts.append(f"Workflow: {links.workflow}")
            if links.action:
                text_parts.append(f"Action: {links.action}")
        
        text = "\n\n".join(text_parts)
        
        # Build tags for filtering/alerting
        tags = [
            "source:nuon",
            "service:datadog-actions-monitor",
            f"action:{action_name.lower().replace(' ', '-')}",
            f"status:{webhook.data.transition}",
            f"org_id:{webhook.nuonorgid}",
            f"install_id:{webhook.data.workflow.owner_id}",
            f"workflow_id:{webhook.data.workflow.id}",
            "event_type:success",
            f"event_level:{'workflow' if is_workflow_summary else 'step'}"
        ]
        
        if webhook.data.step:
            tags.append(f"step_id:{webhook.data.step.id}")
            tags.append(f"step_index:{webhook.data.step.idx}")
            tags.append(f"target_type:{webhook.data.step.target_type}")
            if webhook.data.step.target_id:
                tags.append(f"target_id:{webhook.data.step.target_id}")
            tags.append(f"execution_type:{webhook.data.step.execution_type}")
        
        if webhook.data.workflow:
            tags.append(f"workflow_type:{webhook.data.workflow.type}")
        
        # Build the event payload
        event = {
            "title": title,
            "text": text,
            "alert_type": "info",
            "priority": "low",
            "tags": tags,
            "source_type_name": "nuon",
        }
        
        # Add timestamp if available
        if webhook.time:
            event["date_happened"] = int(
                datetime.fromisoformat(webhook.time.replace('Z', '+00:00')).timestamp()
            )
        
        return event
