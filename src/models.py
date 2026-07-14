"""Pydantic models for Nuon CloudEvents webhook payloads."""

from typing import Optional, List
from pydantic import BaseModel


class Workflow(BaseModel):
    """Workflow information from Nuon webhook."""
    id: str
    type: str  # e.g., "manual_deploy", "provision", "action_workflow_run"
    owner_id: str
    owner_type: str  # e.g., "installs", "apps", "app_branches"


class WorkflowStep(BaseModel):
    """Workflow step details from Nuon webhook."""
    id: str
    name: str
    idx: int
    target_type: Optional[str] = None  # e.g., "install_action_workflow_runs", "install_deploys"
    target_id: Optional[str] = None
    component_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    action_id: Optional[str] = None
    execution_type: str  # e.g., "system", "user", "approval"


class Outcome(BaseModel):
    """Outcome information for completed workflows/steps."""
    status: str  # "succeeded", "failed", "cancelled"
    duration_ms: Optional[int] = None
    error: Optional[str] = None  # Error message if status is "failed"


class Links(BaseModel):
    """Dashboard links from Nuon webhook."""
    org: Optional[str] = None
    install: Optional[str] = None
    workflow: Optional[str] = None
    component: Optional[str] = None
    sandbox: Optional[str] = None
    action: Optional[str] = None


class WebhookData(BaseModel):
    """Data payload from Nuon CloudEvents webhook."""
    kind: str  # "workflow" or "workflow_step"
    transition: str  # "started", "succeeded", "failed", "cancelled"
    org_id: str
    workflow: Workflow
    step: Optional[WorkflowStep] = None  # Present for workflow_step events
    outcome: Optional[Outcome] = None  # Present for terminal events
    links: Optional[Links] = None


class NuonWebhook(BaseModel):
    """Complete Nuon CloudEvents v1.0 webhook payload."""
    specversion: str
    id: str
    type: str  # e.g., "com.nuon.workflow_step.lifecycle.v1"
    source: str
    time: str  # ISO 8601 timestamp
    subject: str
    datacontenttype: str
    nuonorgid: str
    nuonkind: str  # "workflow" or "workflow_step"
    nuontransition: str  # "started", "succeeded", "failed", "cancelled"
    interests: List[str]  # e.g., ["resource:actions", "op:actions.run"]
    data: WebhookData
