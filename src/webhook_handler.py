"""Webhook verification and processing logic."""

import hmac
import hashlib
import logging
from fastapi import Request, HTTPException

from .config import Config
from .models import NuonWebhook
from .integrations.datadog.client import DataDogClient
from .integrations.grafana.client import GrafanaClient

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles Nuon webhook verification and processing."""

    def __init__(self):
        """Initialize the webhook handler with configured integrations."""
        # Initialize all enabled integrations
        self.integrations = []
        
        # DataDog integration
        self.integrations.append(DataDogClient())
        
        # Grafana integration
        self.integrations.append(GrafanaClient())
        
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
        
        # SEND TO INTEGRATIONS
        # No filtering - each integration decides what to do with the webhook
        logger.info(f"Sending webhook to integrations: {webhook.nuonkind} - {webhook.nuontransition}")
        
        await self._send_to_integrations(webhook)
        
        return {
            "status": "processed",
            "message": f"Webhook sent to integrations: {webhook.nuonkind} - {webhook.nuontransition}",
            "kind": webhook.nuonkind,
            "transition": webhook.nuontransition
        }

    async def _send_to_integrations(self, webhook: NuonWebhook) -> bool:
        """
        Send webhook to all configured integrations.
        
        No filtering or routing - just passes the webhook to each integration.
        Each integration decides internally what to do with it.
        
        Args:
            webhook: The parsed Nuon webhook
            
        Returns:
            True if all integrations succeeded
            
        Raises:
            HTTPException: If any integration forwarding fails
        """
        # Send to all configured integrations
        for integration in self.integrations:
            integration_name = integration.__class__.__name__
            
            # Skip disabled integrations
            if not integration.enabled:
                logger.debug(f"Skipping {integration_name} (not enabled)")
                continue
            
            try:
                # Pass empty event_type - integrations handle their own routing
                success = await integration.send(webhook, event_type="")
                if success:
                    logger.info(f"Successfully sent webhook to {integration_name}")
                else:
                    logger.error(f"Failed to send webhook to {integration_name}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to send webhook to {integration_name}"
                    )
            except HTTPException:
                # Re-raise HTTPExceptions from integrations
                raise
            except Exception as e:
                # Catch any unexpected errors
                logger.error(f"Unexpected error sending to {integration_name}: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Unexpected error sending to {integration_name}"
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
