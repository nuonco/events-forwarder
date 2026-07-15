"""Shared utilities for all integrations."""

from typing import Dict
from ..models import NuonWebhook


def extract_metadata(webhook: NuonWebhook) -> Dict[str, str]:
    """
    Extract metadata tags/labels from a Nuon webhook.
    
    This is shared logic used by all integrations (DataDog, Grafana, etc.).
    Each integration can format the output for their specific needs.
    
    Args:
        webhook: The parsed Nuon webhook
        
    Returns:
        Dictionary of metadata key-value pairs
    """
    metadata = {
        "source": "nuon",
        "kind": webhook.nuonkind,
        "transition": webhook.nuontransition,
        "workflow_type": webhook.data.workflow.type,
        "workflow_id": webhook.data.workflow.id,
        "install_id": webhook.data.workflow.owner_id,
        "org_id": webhook.data.org_id,
    }
    
    # Extract resource and operation from interests
    for interest in webhook.interests:
        if interest.startswith("resource:"):
            metadata["resource"] = interest.split(":", 1)[1]
        elif interest.startswith("op:"):
            metadata["operation"] = interest.split(":", 1)[1]
    
    # Add step-specific metadata if this is a step event
    if webhook.data.step:
        metadata["step_id"] = webhook.data.step.id
        metadata["step_name"] = webhook.data.step.name
        metadata["step_idx"] = str(webhook.data.step.idx)
        metadata["execution_type"] = webhook.data.step.execution_type
        
        # Add component_id if available
        if webhook.data.step.component_id:
            metadata["component_id"] = webhook.data.step.component_id
    
    # Add outcome status if terminal
    if webhook.data.outcome and webhook.data.outcome.status:
        metadata["outcome_status"] = webhook.data.outcome.status
    
    return metadata
