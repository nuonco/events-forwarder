"""Webhook verification and processing logic."""

import hmac
import hashlib
import logging
from fastapi import Request, HTTPException

from .config import Config
from .models import NuonWebhook
from .integrations.datadog.client import DataDogClient

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles Nuon webhook verification and processing."""

    def __init__(self):
        """Initialize the webhook handler with configured integrations."""
        # Initialize all enabled integrations
        self.integrations = []
        
        # DataDog integration (always enabled for now)
        self.integrations.append(DataDogClient())
        
        # Future integrations will be added here:
        # if Config.PAGERDUTY_ENABLED:
        #     self.integrations.append(PagerDutyClient())
        
        self.webhook_secret = Config.NUON_WEBHOOK_SECRET

    async def process_webhook(self, request: Request) -> dict:
        """
        Process incoming Nuon webhook.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dictionary with processing status
            
        Raises:
            HTTPException: If verification fails or processing errors occur
        """
        # Get raw body for signature verification
        raw_body = await request.body()
        
        # Verify webhook signature if secret is configured
        if self.webhook_secret:
            signature = request.headers.get("X-Nuon-Signature")
            if not signature:
                logger.warning("Webhook received without signature header")
                raise HTTPException(
                    status_code=401,
                    detail="Missing X-Nuon-Signature header"
                )
            
            if not self._verify_signature(raw_body, signature):
                logger.error("Webhook signature verification failed")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature"
                )
            
            logger.info("Webhook signature verified successfully")
        else:
            logger.warning("Webhook secret not configured - skipping verification")
        
        # Parse the webhook payload
        try:
            payload_dict = await request.json()
            webhook = NuonWebhook(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid webhook payload: {str(e)}"
            )
        
        # Log the webhook receipt
        logger.info(
            f"Received webhook: kind={webhook.nuonkind}, "
            f"transition={webhook.nuontransition}, "
            f"interests={webhook.interests}"
        )
        
        # Debug: Log full webhook structure to identify available fields
        logger.info(f"DEBUG - Workflow data: {webhook.data.workflow}")
        if webhook.data.step:
            logger.info(f"DEBUG - Step data: {webhook.data.step}")
        if webhook.data.outcome:
            logger.info(f"DEBUG - Outcome data: {webhook.data.outcome}")
        if webhook.data.links:
            logger.info(f"DEBUG - Links data: {webhook.data.links}")
        logger.info(f"DEBUG - Full data object: {webhook.data}")
        
        # PROCESS TRACKED EVENTS
        # Send to configured integrations
        
        # ACTION-SPECIFIC PROCESSING
        if webhook.is_action_success():
            action_name = webhook.get_action_name()
            logger.info(f"Processing action success: {action_name}")
            
            # Send to integrations
            await self._send_to_integrations(
                webhook,
                event_type="action",
                event_name=action_name
            )
            
            return {
                "status": "success",
                "message": f"Action success event processed: {action_name}",
                "action": action_name
            }
        
        # COMPONENT-SPECIFIC PROCESSING
        elif webhook.is_component_success():
            component_name = webhook.get_component_name()
            logger.info(f"Processing component success: {component_name}")
            
            # Send to integrations
            await self._send_to_integrations(
                webhook,
                event_type="component",
                event_name=component_name
            )
            
            return {
                "status": "success",
                "message": f"Component success event processed: {component_name}",
                "component": component_name
            }
        
        else:
            # Not a tracked webhook type - log and ignore
            logger.info(
                f"Webhook is not a tracked event (kind={webhook.nuonkind}, "
                f"transition={webhook.nuontransition}, interests={webhook.interests}) - ignoring"
            )
            return {
                "status": "ignored",
                "message": "Not a tracked event - no action taken",
                "kind": webhook.nuonkind,
                "transition": webhook.nuontransition
            }

    async def _send_to_integrations(
        self,
        webhook: NuonWebhook,
        event_type: str,
        event_name: str
    ) -> bool:
        """
        Send webhook to all configured integrations.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Type of event ("action" or "component")
            event_name: Name of the event for logging
            
        Returns:
            True if all integrations succeeded
            
        Raises:
            HTTPException: If any integration forwarding fails
        """
        # Send to all configured integrations
        for integration in self.integrations:
            integration_name = integration.__class__.__name__
            
            try:
                success = await integration.send(webhook, event_type)
                if success:
                    logger.info(f"Sent {event_type} event to {integration_name}: {event_name}")
                else:
                    logger.error(f"Failed to send {event_type} event to {integration_name}: {event_name}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to forward event to {integration_name}"
                    )
            except HTTPException:
                # Re-raise HTTPExceptions from integrations
                raise
            except Exception as e:
                # Catch any unexpected errors
                logger.error(f"Unexpected error sending to {integration_name}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Unexpected error forwarding to {integration_name}"
                )
        
        return True

    def _verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """
        Verify the HMAC-SHA256 signature from Nuon.
        
        Args:
            raw_body: Raw request body bytes
            signature: Signature from X-Nuon-Signature header
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            return False
        
        # Compute HMAC-SHA256 signature
        expected_signature = hmac.new(
            key=self.webhook_secret.encode(),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest().lower()
        
        # Compare signatures (timing-safe comparison)
        return hmac.compare_digest(expected_signature, signature.lower())
