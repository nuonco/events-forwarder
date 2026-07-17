"""Shared utilities for all integrations."""

from typing import Dict
from ..models import NuonWebhook


def extract_metadata(webhook: NuonWebhook) -> Dict[str, str]:
    """
    Extract minimal metadata tags/labels from a Nuon webhook.
    
    Uses only low-cardinality fields to avoid metric explosion.
    All webhook details remain available in DataDog event JSON for investigation.
    
    See README for full webhook payload reference to add additional metadata.
    
    This is shared logic used by all integrations (DataDog, Grafana, etc.).
    Each integration can format the output for their specific needs.
    
    Args:
        webhook: The parsed Nuon webhook
        
    Returns:
        Dictionary of metadata key-value pairs (workflow_type, step_name)
    """
    metadata = {
        "workflow_type": webhook.data.workflow.type,
    }
    
    # Add step_name if this is a step event
    if webhook.data.step and webhook.data.step.name:
        metadata["step_name"] = webhook.data.step.name
    
    return metadata
