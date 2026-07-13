"""DataDog event formatters for Nuon webhooks."""

from typing import Optional, Dict, Any
from datetime import datetime

from ...models import NuonWebhook


# ACTION EVENT FORMATTING
def build_action_event(
    webhook: NuonWebhook,
    action_name: str,
    status_message: str,
    duration: Optional[float]
) -> Dict[str, Any]:
    """
    Build the DataDog event payload for actions.
    
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


# COMPONENT EVENT FORMATTING
def build_component_event(
    webhook: NuonWebhook,
    component_name: str,
    status_message: str,
    duration: Optional[float]
) -> Dict[str, Any]:
    """
    Build the DataDog event payload for component deploys.
    
    Args:
        webhook: The parsed Nuon webhook
        component_name: Name of the component step
        status_message: Success status message
        duration: Duration in seconds (if available)
        
    Returns:
        Dictionary formatted for DataDog Events API
    """
    # Build event title
    title = f"✅ Nuon Component Deploy: {component_name}"
    
    # Build event text with details
    text_parts = [
        f"Component Deploy: {component_name}",
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
    
    # Component steps always have step data
    if webhook.data.step:
        # Add Component ID if present
        if webhook.data.step.component_id:
            text_parts.append(f"Component ID: {webhook.data.step.component_id}")
        
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
        if links.component:
            text_parts.append(f"Component: {links.component}")
        if links.workflow:
            text_parts.append(f"Workflow: {links.workflow}")
    
    text = "\n\n".join(text_parts)
    
    # Build tags for filtering/alerting
    tags = [
        "source:nuon",
        "service:datadog-actions-monitor",
        "resource_type:components",
        f"component:{component_name.lower().replace(' ', '-')}",
        f"status:{webhook.data.transition}",
        f"org_id:{webhook.nuonorgid}",
        f"install_id:{webhook.data.workflow.owner_id}",
        f"workflow_id:{webhook.data.workflow.id}",
        f"workflow_type:{webhook.data.workflow.type}",
        "event_type:success",
        "event_level:step"
    ]
    
    if webhook.data.step:
        tags.append(f"step_id:{webhook.data.step.id}")
        tags.append(f"step_index:{webhook.data.step.idx}")
        
        if webhook.data.step.component_id:
            tags.append(f"component_id:{webhook.data.step.component_id}")
        
        if webhook.data.step.target_type:
            tags.append(f"target_type:{webhook.data.step.target_type}")
        if webhook.data.step.target_id:
            tags.append(f"target_id:{webhook.data.step.target_id}")
        
        tags.append(f"execution_type:{webhook.data.step.execution_type}")
    
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
