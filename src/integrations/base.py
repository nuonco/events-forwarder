"""Base integration class for all external service integrations."""

from typing import Protocol
from ..models import NuonWebhook


class BaseIntegration(Protocol):
    """
    Base protocol that all integrations must implement.
    
    This ensures all integrations have a consistent interface for
    sending webhooks to external services.
    """
    
    async def send(self, webhook: NuonWebhook, event_type: str) -> bool:
        """
        Send webhook data to the external integration.
        
        Args:
            webhook: The parsed Nuon webhook
            event_type: Type of event ("action" or "component")
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            HTTPException: If forwarding fails
        """
        ...
