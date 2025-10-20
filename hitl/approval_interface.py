"""Approval interface models and utilities for HITL system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApprovalStatus(str, Enum):
    """Status of approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalRequest(BaseModel):
    """Model for approval request data."""

    request_id: str
    agent_id: str
    checkpoint_id: str
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict)
    question: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    created_at: datetime
    timeout_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING


class ApprovalResponse(BaseModel):
    """Model for approval response data."""

    request_id: str
    checkpoint_id: str
    approved: bool
    reviewer_notes: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    reviewer_id: Optional[str] = None


class ApprovalDashboardData(BaseModel):
    """Model for approval dashboard data."""

    pending_count: int
    approved_count: int
    rejected_count: int
    timeout_count: int
    average_response_time_seconds: float
    pending_requests: list[ApprovalRequest]


def format_approval_request_for_display(request: ApprovalRequest) -> str:
    """
    Format approval request for human-readable display.

    Args:
        request: Approval request to format

    Returns:
        Formatted string for display
    """
    lines = [
        f"Approval Request: {request.request_id}",
        f"Status: {request.status.value}",
        f"Agent: {request.agent_id}",
        f"Reason: {request.reason}",
        f"Created: {request.created_at.isoformat()}",
        f"Timeout: {request.timeout_at.isoformat()}",
        "",
    ]

    if request.question:
        lines.extend(["Question:", request.question, ""])

    if request.context:
        lines.extend(["Context:", str(request.context), ""])

    if request.options:
        lines.extend(["Options:", str(request.options), ""])

    return "\n".join(lines)

