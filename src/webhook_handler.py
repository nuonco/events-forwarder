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
        """Initialize the webhook handler."""
        self.datadog_client = DataDogClient()
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
        
        # ACTION-SPECIFIC PROCESSING
        if webhook.is_action_success():
            action_name = webhook.get_action_name()
            logger.info(f"Processing action success: {action_name}")
            
            # Send to DataDog
            success = await self.datadog_client.send_action_success_event(webhook)
            
            if success:
                return {
                    "status": "success",
                    "message": f"Action success event sent to DataDog: {action_name}",
                    "action": action_name
                }
            else:
                logger.error(f"Failed to send action success to DataDog: {action_name}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to send event to DataDog"
                )
        
        # COMPONENT-SPECIFIC PROCESSING
        elif webhook.is_component_success():
            component_name = webhook.get_component_name()
            logger.info(f"Processing component success: {component_name}")
            
            # Send to DataDog
            success = await self.datadog_client.send_component_success_event(webhook)
            
            if success:
                return {
                    "status": "success",
                    "message": f"Component success event sent to DataDog: {component_name}",
                    "component": component_name
                }
            else:
                logger.error(f"Failed to send component success to DataDog: {component_name}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to send event to DataDog"
                )
        
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
